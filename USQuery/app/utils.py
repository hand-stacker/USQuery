
def makeFullName(first_name, last_name, middle_name=None, suffix=None, short_title=None):
    full_name = ""
    if (short_title is not None):
        full_name += short_title + " "
    full_name += first_name
    if (middle_name is not None):
        full_name += " " + middle_name 
    full_name += " " + last_name
    if (suffix is not None):
        full_name += " " + suffix
    return full_name
