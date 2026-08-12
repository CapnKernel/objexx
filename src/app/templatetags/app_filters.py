from django import template
from django.db.models import Model

register = template.Library()


@register.filter
def join_model_ids(value, arg=','):
    """Return a separator-joined string of the primary keys of a list of model instances.

    All elements must be instances of the same model type.
    """
    instances = list(value)
    if not instances:
        return ''

    model_type = type(instances[0])
    if not issubclass(model_type, Model):
        raise template.TemplateSyntaxError('The "ids" filter expects model instances.')

    for instance in instances:
        if not isinstance(instance, model_type):
            raise template.TemplateSyntaxError('The "ids" filter expects all elements to be the same model type.')

    return arg.join(str(instance.pk) for instance in instances)
