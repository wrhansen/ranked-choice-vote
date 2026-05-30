# ranked-choice-vote

Ranked Choice Voting Application -- originally designed for book club voting but
can serve any general purpose ranked-choice voting needs.

## Technology Stack

* Docker container & docker compose environment for local development
* python 3.14
* Django 5.2
* Sqlite database
* Htmx application
* github action for building/deploying to
* Deploy container to fly.io


## Features

* Allow anonymous user (by IP address) to submit Vote in ACTIVE Poll
* Django admin page to create new Options, and add them to Poll
* Django admin feature to copy over Options from previous Poll, except for
  winner
* Django admin has copy link button to share to users when Poll is ACTIVE
* Django admin allows changing state of NEW Poll to ACTIVE and changing state of
  ACTIVE Poll to Closed
* Home page lists all polls, filters for finished polls and stuff
* Vote page allows for user to voting in ACTIVE Poll state (after clicking join
  button)
* ACTIVE poll Vote page shows how many current users joined, and how many have
  submitted their vote
* Vote page Options displayed as Image cards (Image + Text) giving user simple
  drag n drop functionality to reorder everything
* Vote page shows results once Poll set to Closed (by Django Admin superuser)
* Light & Dark theme selector (defaulting to system choice) -- Solarized Light &
  Dark theme

## Domain

* Poll is an event that has several states: NEW, ACTIVE, CLOSED
* User can join a Poll in ACTIVE state.
* User can submit a Vote on a Poll that they have joined that is in ACTIVE
  state.
* Vote is an array of Options, ranked in order of preference
* Option is a thing to vote on, consists of text and image

