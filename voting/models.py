import uuid

from django.db import models


class OptionsPool(models.Model):
    name = models.CharField(max_length=255)
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return self.name

    class Meta:
        ordering = ["-created_at"]


class Option(models.Model):
    pool = models.ForeignKey(OptionsPool, on_delete=models.CASCADE, related_name="options")
    title = models.CharField(max_length=255)
    image = models.ImageField(upload_to="options/", blank=True)
    order = models.PositiveIntegerField(default=0)

    def __str__(self):
        return self.title

    class Meta:
        ordering = ["order"]


class Poll(models.Model):
    class State(models.TextChoices):
        NEW = "NEW", "New"
        ACTIVE = "ACTIVE", "Active"
        CLOSED = "CLOSED", "Closed"

    class Algorithm(models.TextChoices):
        IRV = "IRV", "Instant Runoff Voting"
        BORDA = "BORDA", "Borda Count"
        CONDORCET = "CONDORCET", "Condorcet (Schulze)"

    id = models.UUIDField(primary_key=True, default=uuid.uuid4, editable=False)
    title = models.CharField(max_length=255)
    state = models.CharField(max_length=10, choices=State.choices, default=State.NEW)
    algorithm = models.CharField(max_length=10, choices=Algorithm.choices)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    closed_at = models.DateTimeField(null=True, blank=True)
    options_pool = models.ForeignKey(
        OptionsPool, on_delete=models.SET_NULL, null=True, blank=True, related_name="polls"
    )

    def __str__(self):
        return f"{self.title} ({self.get_state_display()})"

    @property
    def options(self):
        if self.options_pool_id:
            return self.options_pool.options
        return Option.objects.none()

    def compute_results(self):
        from .algorithms import ALGORITHMS

        votes = list(self.votes.values_list("rankings", flat=True))
        options = list(self.options.order_by("order"))
        algo = ALGORITHMS[self.algorithm]()
        return algo.compute(votes, options)

    class Meta:
        ordering = ["-created_at"]


class UserPoll(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="participants")
    name = models.CharField(max_length=100)
    session_key = models.CharField(max_length=40)
    ip_address = models.GenericIPAddressField()
    joined_at = models.DateTimeField(auto_now_add=True)
    has_voted = models.BooleanField(default=False)

    def __str__(self):
        return f"{self.name} on {self.poll}"

    class Meta:
        unique_together = [("poll", "session_key")]


class Vote(models.Model):
    poll = models.ForeignKey(Poll, on_delete=models.CASCADE, related_name="votes")
    user_poll = models.OneToOneField(UserPoll, on_delete=models.CASCADE, related_name="vote")
    rankings = models.JSONField()  # ordered list of Option PKs, index 0 = 1st choice
    submitted_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"Vote by {self.user_poll.name} on {self.poll}"
