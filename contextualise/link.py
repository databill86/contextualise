import maya
from flask import Blueprint, session, render_template, request, flash, url_for, redirect
from flask_login import current_user
from flask_security import login_required
from topicdb.core.models.attribute import Attribute
from topicdb.core.models.datatype import DataType
from topicdb.core.models.occurrence import Occurrence
from topicdb.core.store.retrievalmode import RetrievalMode
from werkzeug.exceptions import abort

from contextualise.topic_store import get_topic_store

bp = Blueprint("link", __name__)


@bp.route("/links/<map_identifier>/<topic_identifier>")
@login_required
def index(map_identifier, topic_identifier):
    topic_store = get_topic_store()
    topic_map = topic_store.get_topic_map(map_identifier)

    if topic_map is None:
        abort(404)

    if current_user.id != topic_map.user_identifier:
        abort(403)

    topic = topic_store.get_topic(
        map_identifier,
        topic_identifier,
        resolve_attributes=RetrievalMode.RESOLVE_ATTRIBUTES,
    )
    if topic is None:
        abort(404)

    link_occurrences = topic_store.get_topic_occurrences(
        map_identifier,
        topic_identifier,
        "url",
        resolve_attributes=RetrievalMode.RESOLVE_ATTRIBUTES,
    )

    links = []
    for link_occurrence in link_occurrences:
        links.append(
            {
                "identifier": link_occurrence.identifier,
                "title": link_occurrence.get_attribute_by_name("title").value,
                "scope": link_occurrence.scope,
                "url": link_occurrence.resource_ref,
            }
        )

    # occurrences_stats = topic_store.get_topic_occurrences_statistics(map_identifier, topic_identifier)

    creation_date_attribute = topic.get_attribute_by_name("creation-timestamp")
    creation_date = (
        maya.parse(creation_date_attribute.value)
        if creation_date_attribute
        else "Undefined"
    )

    return render_template(
        "link/index.html",
        topic_map=topic_map,
        topic=topic,
        links=links,
        creation_date=creation_date,
    )


@bp.route("/links/add/<map_identifier>/<topic_identifier>", methods=("GET", "POST"))
@login_required
def add(map_identifier, topic_identifier):
    topic_store = get_topic_store()
    topic_map = topic_store.get_topic_map(map_identifier)

    if topic_map is None:
        abort(404)

    if current_user.id != topic_map.user_identifier:
        abort(403)

    topic = topic_store.get_topic(
        map_identifier,
        topic_identifier,
        resolve_attributes=RetrievalMode.RESOLVE_ATTRIBUTES,
    )
    if topic is None:
        abort(404)

    form_link_title = ""
    form_link_url = ""
    form_link_scope = session["current_scope"]

    error = 0

    if request.method == "POST":
        form_link_title = request.form["link-title"].strip()
        form_link_url = request.form["link-url"].strip()
        form_link_scope = request.form["link-scope"].strip()

        # If no values have been provided set their default values
        if not form_link_scope:
            form_link_scope = "*"  # Universal scope

        # Validate form inputs
        if not form_link_title:
            error = error | 1
        if not form_link_url:
            error = error | 2
        if not topic_store.topic_exists(topic_map.identifier, form_link_scope):
            error = error | 4

        if error != 0:
            flash(
                "An error occurred when submitting the form. Please review the warnings and fix accordingly.",
                "warning",
            )
        else:
            link_occurrence = Occurrence(
                instance_of="url",
                topic_identifier=topic.identifier,
                scope=form_link_scope,
                resource_ref=form_link_url,
            )
            title_attribute = Attribute(
                "title",
                form_link_title,
                link_occurrence.identifier,
                data_type=DataType.STRING,
            )

            # Persist objects to the topic store
            topic_store.set_occurrence(topic_map.identifier, link_occurrence)
            topic_store.set_attribute(topic_map.identifier, title_attribute)

            flash("Link successfully added.", "success")
            return redirect(
                url_for(
                    "link.index",
                    map_identifier=topic_map.identifier,
                    topic_identifier=topic.identifier,
                )
            )

    return render_template(
        "link/add.html",
        error=error,
        topic_map=topic_map,
        topic=topic,
        link_title=form_link_title,
        link_url=form_link_url,
        link_scope=form_link_scope,
    )


@bp.route(
    "/links/edit/<map_identifier>/<topic_identifier>/<link_identifier>",
    methods=("GET", "POST"),
)
@login_required
def edit(map_identifier, topic_identifier, link_identifier):
    topic_store = get_topic_store()
    topic_map = topic_store.get_topic_map(map_identifier)

    if topic_map is None:
        abort(404)

    if current_user.id != topic_map.user_identifier:
        abort(403)

    topic = topic_store.get_topic(
        map_identifier,
        topic_identifier,
        resolve_attributes=RetrievalMode.RESOLVE_ATTRIBUTES,
    )
    if topic is None:
        abort(404)

    link_occurrence = topic_store.get_occurrence(
        map_identifier,
        link_identifier,
        resolve_attributes=RetrievalMode.RESOLVE_ATTRIBUTES,
    )

    form_link_title = link_occurrence.get_attribute_by_name("title").value
    form_link_scope = link_occurrence.scope

    error = 0

    if request.method == "POST":
        form_link_title = request.form["link-title"].strip()
        form_link_scope = request.form["link-scope"].strip()

        # If no values have been provided set their default values
        if not form_link_scope:
            form_link_scope = "*"  # Universal scope

        # Validate form inputs
        if not form_link_title:
            error = error | 1
        if not topic_store.topic_exists(topic_map.identifier, form_link_scope):
            error = error | 2

        if error != 0:
            flash(
                "An error occurred when submitting the form. Please review the warnings and fix accordingly.",
                "warning",
            )
        else:
            # Update link's title if it has changed
            if link_occurrence.get_attribute_by_name("title").value != form_link_title:
                topic_store.update_attribute_value(
                    topic_map.identifier,
                    link_occurrence.get_attribute_by_name("title").identifier,
                    form_link_title,
                )

            # Update link's scope if it has changed
            if link_occurrence.scope != form_link_scope:
                topic_store.update_occurrence_scope(
                    map_identifier, link_occurrence.identifier, form_link_scope
                )

            flash("Link successfully updated.", "success")
            return redirect(
                url_for(
                    "link.index",
                    map_identifier=topic_map.identifier,
                    topic_identifier=topic.identifier,
                )
            )

    return render_template(
        "link/edit.html",
        error=error,
        topic_map=topic_map,
        topic=topic,
        link_identifier=link_occurrence.identifier,
        link_title=form_link_title,
        link_scope=form_link_scope,
    )


@bp.route(
    "/links/delete/<map_identifier>/<topic_identifier>/<link_identifier>",
    methods=("GET", "POST"),
)
@login_required
def delete(map_identifier, topic_identifier, link_identifier):
    topic_store = get_topic_store()
    topic_map = topic_store.get_topic_map(map_identifier)

    if topic_map is None:
        abort(404)

    if current_user.id != topic_map.user_identifier:
        abort(403)

    topic = topic_store.get_topic(
        map_identifier,
        topic_identifier,
        resolve_attributes=RetrievalMode.RESOLVE_ATTRIBUTES,
    )
    if topic is None:
        abort(404)

    link_occurrence = topic_store.get_occurrence(
        map_identifier,
        link_identifier,
        resolve_attributes=RetrievalMode.RESOLVE_ATTRIBUTES,
    )

    form_link_title = link_occurrence.get_attribute_by_name("title").value
    form_link_scope = link_occurrence.scope

    if request.method == "POST":
        # Delete link occurrence from topic store
        topic_store.delete_occurrence(map_identifier, link_occurrence.identifier)

        flash("Link successfully deleted.", "warning")
        return redirect(
            url_for(
                "link.index",
                map_identifier=topic_map.identifier,
                topic_identifier=topic.identifier,
            )
        )

    return render_template(
        "link/delete.html",
        topic_map=topic_map,
        topic=topic,
        link_identifier=link_occurrence.identifier,
        link_title=form_link_title,
        link_scope=form_link_scope,
    )
