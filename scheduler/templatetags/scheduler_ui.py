from django import template

from scheduler.forms import ManualSessionForm

register = template.Library()


@register.simple_tag(takes_context=True)
def manual_session_form(context):
    """Return a bound manual-session form restored from session state if present."""
    request = context['request']
    form_data = request.session.pop('manual_session_form_data', None)
    form_errors = request.session.pop('manual_session_form_errors', None)
    if form_data:
        form = ManualSessionForm(form_data)
        if form_errors:
            for error in form_errors:
                form.add_error(None, error)
        request.session.modified = True
        return form
    return ManualSessionForm()
