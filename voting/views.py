import json
import time

from django.http import HttpResponseBadRequest, StreamingHttpResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.template.loader import render_to_string
from django.views.decorators.http import require_GET, require_POST

from .models import Poll, UserPoll, Vote


def _get_client_ip(request):
    forwarded = request.META.get("HTTP_X_FORWARDED_FOR")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.META.get("REMOTE_ADDR", "127.0.0.1")


def _get_user_poll(request, poll):
    if not request.session.session_key:
        return None
    return UserPoll.objects.filter(
        poll=poll,
        session_key=request.session.session_key,
    ).first()


@require_GET
def home(request):
    state_filter = request.GET.get("state", "")
    polls = Poll.objects.all()
    if state_filter in Poll.State.values:
        polls = polls.filter(state=state_filter)
    context = {"polls": polls, "state_filter": state_filter, "states": Poll.State}
    if request.headers.get("HX-Request"):
        return render(request, "voting/_polls_content.html", context)
    return render(request, "voting/home.html", context)


@require_GET
def poll_detail(request, pk):
    poll = get_object_or_404(Poll, pk=pk)
    user_poll = _get_user_poll(request, poll)

    results = None
    if poll.state == Poll.State.CLOSED and poll.votes.exists():
        results = poll.compute_results()
        # Pre-build template-friendly matrix rows for Condorcet results
        if poll.algorithm == Poll.Algorithm.CONDORCET and results:
            opts = results["summary"]["options"]
            matrix = results["summary"]["matrix"]
            results["summary"]["matrix_rows"] = [
                {
                    "option": opt_i,
                    "cells": [
                        None if opt_i.pk == opt_j.pk else matrix[opt_i.pk][opt_j.pk]
                        for opt_j in opts
                    ],
                }
                for opt_i in opts
            ]

    context = {
        "poll": poll,
        "user_poll": user_poll,
        "options": poll.options.order_by("order"),
        "results": results,
    }
    if request.headers.get("HX-Request"):
        return render(request, "voting/_poll_detail.html", context)
    return render(request, "voting/poll.html", context)


@require_POST
def join(request, pk):
    poll = get_object_or_404(Poll, pk=pk)

    if poll.state != Poll.State.ACTIVE:
        return HttpResponseBadRequest("Poll is not active.")

    name = request.POST.get("name", "").strip()
    if not name:
        return HttpResponseBadRequest("Name is required.")

    if not request.session.session_key:
        request.session.create()

    user_poll, _ = UserPoll.objects.get_or_create(
        poll=poll,
        session_key=request.session.session_key,
        defaults={
            "name": name,
            "ip_address": _get_client_ip(request),
        },
    )

    return render(request, "voting/_join_confirm.html", {
        "poll": poll,
        "user_poll": user_poll,
        "options": poll.options.order_by("order"),
    })


@require_POST
def vote(request, pk):
    poll = get_object_or_404(Poll, pk=pk)

    if poll.state != Poll.State.ACTIVE:
        return HttpResponseBadRequest("Poll is not active.")

    user_poll = _get_user_poll(request, poll)
    if not user_poll:
        return HttpResponseBadRequest("You have not joined this poll.")

    if user_poll.has_voted:
        return HttpResponseBadRequest("You have already voted.")

    raw = request.POST.get("rankings", "")
    try:
        rankings = json.loads(raw)
        if not isinstance(rankings, list):
            raise ValueError
        rankings = [int(pk) for pk in rankings]
    except (ValueError, TypeError):
        return HttpResponseBadRequest("Invalid rankings format.")

    valid_pks = set(poll.options.values_list("pk", flat=True))
    if not rankings or not all(pk in valid_pks for pk in rankings):
        return HttpResponseBadRequest("Rankings contain invalid options.")

    Vote.objects.create(poll=poll, user_poll=user_poll, rankings=rankings)
    user_poll.has_voted = True
    user_poll.save(update_fields=["has_voted"])

    return render(request, "voting/_voted_confirm.html", {"poll": poll, "user_poll": user_poll})


@require_GET
def poll_stream(request, pk):
    poll = get_object_or_404(Poll, pk=pk)

    def event_stream():
        while True:
            try:
                current_poll = Poll.objects.prefetch_related("participants").get(pk=pk)
            except Poll.DoesNotExist:
                break

            participants = list(current_poll.participants.order_by("joined_at"))
            html = render_to_string(
                "voting/_poll_status.html",
                {
                    "poll": current_poll,
                    "participants": participants,
                    "joined_count": len(participants),
                    "voted_count": sum(1 for p in participants if p.has_voted),
                },
                request=request,
            )

            data_lines = "\n".join(f"data: {line}" for line in html.splitlines())
            yield f"event: poll-status\n{data_lines}\n\n"

            if current_poll.state == Poll.State.CLOSED:
                yield "event: poll-closed\ndata: \n\n"
                break

            time.sleep(2)

    response = StreamingHttpResponse(event_stream(), content_type="text/event-stream")
    response["Cache-Control"] = "no-cache"
    response["X-Accel-Buffering"] = "no"
    return response
