from django import template

register = template.Library()


@register.filter
def get_dict_value(dictionary, key):
    """Lookup a key on a dict in templates — e.g. {{ stages|get_dict_value:stage }}."""
    if isinstance(dictionary, dict):
        return dictionary.get(key)
    return None
