# reclutamiento/templatetags/report_tags.py

from django import template

register = template.Library()

@register.filter(name='get_item')
def get_item(dictionary, key):
    """
    Permite obtener un valor de un diccionario usando una variable como llave en las plantillas.
    Uso: {{ mi_diccionario|get_item:mi_llave }}
    """
    return dictionary.get(key)