"""templating.py
RSSNotifier allows you to template your emails using Jinja markup.
This file includes some helper functions."""

import logging
from typing import List, Tuple, Set

import jinja2
from lxml import etree

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.DEBUG)


def load_jinja_template(
    template_directory: str, template_filename: str
) -> jinja2.Template:
    """Loads a Jinja template given its filename and base directory.
    :param template_directory: The base directory of the template.

    :param template_filename: The base filename of the template.
    """
    file_system_loader = jinja2.FileSystemLoader(searchpath=template_directory)
    template_environment = jinja2.Environment(loader=file_system_loader)
    return template_environment.get_template(template_filename)


def fill_out_new_post_template(
    template: jinja2.Template,
    email_address: str,
    unsubscribe_url: str,
    item_to_notify_about: dict,
) -> Set[str]:
    """Fills out a template for email body content about a new post.

    :param template: The loaded template to fill out.

    :param email_address: The email address to send the email to.

    :param unsubscribe_url: Where to unsubscribe (this is not an optional argument to encourage not sending spam)

    :param item_to_notify_about: A dictionary with information about the RSS item you're notifying about.
    Should have the keys  "published_at" "title", "link", and "description", but it somewhat depends on your template definitions.

    :returns The template loaded both as HTML and as raw text."""
    rendered_template = template.render(
        {
            "email_address": email_address,
            "unsubscribe_url": unsubscribe_url,
            "item": item_to_notify_about,
        }
    )
    logger.debug(f"Rendered template: {rendered_template}")
    # Extract raw text from the template
    template_tree = etree.fromstring(rendered_template)
    raw_template_text = "".join(template_tree.itertext())
    return {rendered_template, raw_template_text}
