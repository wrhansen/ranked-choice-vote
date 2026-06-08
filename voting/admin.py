import os

from django.contrib import admin, messages
from django.http import JsonResponse
from django.shortcuts import get_object_or_404
from django.urls import path, reverse
from django.utils import timezone
from django.utils.html import format_html, mark_safe

from .models import Option, OptionsPool, Poll, UserPoll, Vote


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


@admin.register(OptionsPool)
class OptionsPoolAdmin(admin.ModelAdmin):
    list_display = ["name", "option_count", "created_at"]
    readonly_fields = ["created_at"]
    fields = ["name", "created_at"]
    inlines = [OptionInline]
    actions = ["copy_pool"]

    @admin.display(description="Options")
    def option_count(self, obj):
        return obj.options.count()

    @admin.action(description="Copy selected pools")
    def copy_pool(self, request, queryset):
        for pool in queryset:
            new_pool = OptionsPool.objects.create(name=f"{pool.name} (copy)")
            for opt in pool.options.all():
                Option.objects.create(
                    pool=new_pool,
                    title=opt.title,
                    image=opt.image.name if opt.image else "",
                    order=opt.order,
                )
        self.message_user(request, f"Copied {queryset.count()} pool(s).")

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "<int:pool_id>/upload/",
                self.admin_site.admin_view(self.upload_images),
                name="optionspool_upload",
            ),
        ]
        return custom + urls

    def upload_images(self, request, pool_id):
        if request.method != "POST":
            return JsonResponse({"error": "POST required"}, status=405)
        pool = get_object_or_404(OptionsPool, pk=pool_id)
        created = []
        for f in request.FILES.getlist("images"):
            title = os.path.splitext(f.name)[0]
            opt = Option(pool=pool, title=title, order=pool.options.count())
            opt.image.save(f.name, f, save=True)
            created.append({"id": opt.pk, "title": opt.title})
        return JsonResponse({"created": created})


@admin.register(Poll)
class PollAdmin(admin.ModelAdmin):
    list_display = ["title", "state", "algorithm", "created_at", "participant_count", "voted_count"]
    readonly_fields = ["id", "created_at", "closed_at", "share_link", "results_display"]
    fields = [
        "title", "state", "algorithm", "options_pool",
        "share_link", "id", "created_at", "closed_at", "results_display",
    ]
    actions = ["activate_poll", "close_poll"]

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
        path_val = reverse("poll-detail", args=[obj.pk])
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
            path=path_val,
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


@admin.register(UserPoll)
class UserPollAdmin(admin.ModelAdmin):
    list_display = ["name", "poll", "joined_at", "has_voted", "ip_address"]
    list_filter = ["poll", "has_voted"]
    readonly_fields = ["poll", "name", "session_key", "ip_address", "joined_at", "has_voted"]


@admin.register(Vote)
class VoteAdmin(admin.ModelAdmin):
    list_display = ["user_poll", "poll", "submitted_at"]
    readonly_fields = ["poll", "user_poll", "rankings", "submitted_at"]
