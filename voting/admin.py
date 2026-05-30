from django.contrib import admin, messages
from django.urls import reverse
from django.utils import timezone
from django.utils.html import format_html, mark_safe

from .models import Option, Poll, UserPoll, Vote


class OptionInline(admin.StackedInline):
    model = Option
    extra = 1
    fields = ["title", "image", "image_preview", "order"]
    readonly_fields = ["image_preview"]

    def image_preview(self, obj):
        if obj.pk and obj.image:
            return format_html('<img src="{}" style="max-height:80px;">', obj.image.url)
        return "—"
    image_preview.short_description = "Preview"


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ["title", "state", "algorithm", "created_at", "participant_count", "voted_count"]
    readonly_fields = ["id", "created_at", "closed_at", "share_link", "results_display"]
    fields = ["title", "state", "algorithm", "share_link", "id", "created_at", "closed_at", "results_display"]
    inlines = [OptionInline]
    actions = ["activate_poll", "close_poll", "copy_options_from_previous"]

    # ------------------------------------------------------------------ #
    # list_display helpers                                                 #
    # ------------------------------------------------------------------ #

    @admin.display(description="Joined")
    def participant_count(self, obj):
        return obj.participants.count()

    @admin.display(description="Voted")
    def voted_count(self, obj):
        return obj.participants.filter(has_voted=True).count()

    # ------------------------------------------------------------------ #
    # readonly field: share link                                           #
    # ------------------------------------------------------------------ #

    @admin.display(description="Share Link")
    def share_link(self, obj):
        if not obj.pk:
            return "Save the poll first to get a share link."
        path = reverse("poll-detail", args=[obj.pk])
        uid = str(obj.pk).replace("-", "")[:12]
        return format_html(
            '<input id="share-{uid}" value="{path}" readonly style="width:380px;font-family:monospace;">'
            ' <button type="button" onclick="'
            "var el=document.getElementById('share-{uid}');"
            "el.value=window.location.origin+'{path}';"
            "navigator.clipboard.writeText(el.value);"
            "this.textContent='Copied!';"
            '">Copy Link</button>',
            uid=uid,
            path=path,
        )

    # ------------------------------------------------------------------ #
    # readonly field: results                                              #
    # ------------------------------------------------------------------ #

    @admin.display(description="Results")
    def results_display(self, obj):
        if obj.state != Poll.State.CLOSED:
            return "Available once the poll is closed."
        if not obj.votes.exists():
            return "No votes were submitted."

        results = obj.compute_results()
        winner = results["winner"]
        summary = results["summary"]

        html = f"<strong>Winner: {winner.title}</strong><br><br>"

        if obj.algorithm == Poll.Algorithm.IRV:
            html += (
                "<table style='border-collapse:collapse'>"
                "<tr><th style='padding:4px 8px'>Round</th>"
                "<th style='padding:4px 8px'>Tallies</th>"
                "<th style='padding:4px 8px'>Eliminated</th></tr>"
            )
            for i, rnd in enumerate(summary["rounds"], 1):
                tallies_str = ", ".join(f"{o.title}: {c}" for o, c in rnd["tallies"])
                eliminated = rnd["eliminated"].title if rnd["eliminated"] else "—"
                html += (
                    f"<tr><td style='padding:4px 8px'>{i}</td>"
                    f"<td style='padding:4px 8px'>{tallies_str}</td>"
                    f"<td style='padding:4px 8px'>{eliminated}</td></tr>"
                )
            html += "</table>"

        elif obj.algorithm == Poll.Algorithm.BORDA:
            html += "<table style='border-collapse:collapse'><tr><th style='padding:4px 8px'>Option</th><th style='padding:4px 8px'>Points</th></tr>"
            for option, pts in summary["scores"]:
                html += f"<tr><td style='padding:4px 8px'>{option.title}</td><td style='padding:4px 8px'>{pts}</td></tr>"
            html += "</table>"

        elif obj.algorithm == Poll.Algorithm.CONDORCET:
            opts = summary["options"]
            matrix = summary["matrix"]
            html += "<table style='border-collapse:collapse'><tr><th style='padding:4px 8px'></th>"
            for o in opts:
                html += f"<th style='padding:4px 8px'>{o.title}</th>"
            html += "</tr>"
            for o in opts:
                html += f"<tr><td style='padding:4px 8px'><strong>{o.title}</strong></td>"
                for other in opts:
                    if o.pk == other.pk:
                        html += "<td style='padding:4px 8px;text-align:center'>—</td>"
                    else:
                        cell = matrix[o.pk][other.pk]
                        html += f"<td style='padding:4px 8px;text-align:center'>{cell['prefer']}–{cell['against']}</td>"
                html += "</tr>"
            html += "</table>"

        return mark_safe(html)

    # ------------------------------------------------------------------ #
    # actions                                                              #
    # ------------------------------------------------------------------ #

    @admin.action(description="Activate selected polls (NEW → ACTIVE)")
    def activate_poll(self, request, queryset):
        updated = queryset.filter(state=Poll.State.NEW).update(state=Poll.State.ACTIVE)
        self.message_user(request, f"{updated} poll(s) activated.")

    @admin.action(description="Close selected polls (ACTIVE → CLOSED)")
    def close_poll(self, request, queryset):
        updated = queryset.filter(state=Poll.State.ACTIVE).update(
            state=Poll.State.CLOSED,
            closed_at=timezone.now(),
        )
        self.message_user(request, f"{updated} poll(s) closed.")

    @admin.action(description="Copy options from most recent closed poll (excluding winner)")
    def copy_options_from_previous(self, request, queryset):
        previous = (
            Poll.objects.filter(state=Poll.State.CLOSED)
            .exclude(pk__in=queryset.values_list("pk", flat=True))
            .order_by("-closed_at")
            .first()
        )

        if not previous:
            self.message_user(request, "No previous closed poll found.", level=messages.WARNING)
            return

        if not previous.votes.exists():
            self.message_user(
                request,
                f"'{previous}' has no votes — cannot determine winner to exclude.",
                level=messages.WARNING,
            )
            return

        results = previous.compute_results()
        winner = results["winner"]
        options_to_copy = previous.options.exclude(pk=winner.pk)

        for target_poll in queryset:
            for opt in options_to_copy:
                Option.objects.get_or_create(
                    poll=target_poll,
                    title=opt.title,
                    defaults={"image": opt.image.name if opt.image else "", "order": opt.order},
                )

        self.message_user(
            request,
            f"Copied {options_to_copy.count()} option(s) from '{previous}' "
            f"(excluded winner: {winner.title}) to {queryset.count()} poll(s).",
        )


@admin.register(UserPoll)
class UserPollAdmin(admin.ModelAdmin):
    list_display = ["name", "poll", "joined_at", "has_voted", "ip_address"]
    list_filter = ["poll", "has_voted"]
    readonly_fields = ["poll", "name", "session_key", "ip_address", "joined_at", "has_voted"]


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ["user_poll", "poll", "submitted_at"]
    readonly_fields = ["poll", "user_poll", "rankings", "submitted_at"]
