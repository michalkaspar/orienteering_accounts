from django import template

register = template.Library()


@register.filter
def qualified_count_before(roasters, index):
    """Count the number of qualified roasters before the given index"""
    count = 0
    for i in range(index):
        if roasters[i].is_qualified:
            count += 1
    return count + 1  # Add 1 for 1-based numbering


@register.filter
def qualified_count_equals(counter, roasters):
    """Check if the qualified count at this position equals a specific value"""
    count = 0
    for i in range(counter):
        if roasters[i].is_qualified:
            count += 1
    return count
