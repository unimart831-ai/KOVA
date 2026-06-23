from django import template

from apps.leads.professional_funnel import consult_funnel_stage_label

register = template.Library()


@register.filter
def consult_funnel_label(lead):
    return consult_funnel_stage_label(lead)
