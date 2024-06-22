# RSS Notifier

## Introduction
RSS Notifier is a quick script with a simple API which allows people to subscribe to email updates every time a RSS feed changes.

It also includes a script for sending out notification emails.

Used for my blog, see https://blog.albins.website/email_subscription.

With Jinja templating for flexibility.

## Setup

The notifier currently uses FaunaDB for data storage, Mailersend for email sending and MyEmailVerifier for email validation,
but it should be easily extendable to add any service you'd like.

Aside from that, setup is hopefully quite straightforward:

1. Copy `config.toml.example` to `config.toml`, then customize it for your needs, assuming you've gathered API keys for the respective service mentioned above.
2. Customize `email_templates` for your needs. The current example template is in Swedish and is for my blog so you most likely need to change it.

## Hosting

Using Deta.dev, you can host the site by running:

`deta new` to create a new project and then

`deta push` to deploy the app.

Two commands, very magic.