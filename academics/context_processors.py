from .models import AcademicSession, Term

def academic_context(request):
    """
    Globally available academic context variables.
    Returns the currently active session and term.
    """
    return {
        'current_session': AcademicSession.get_current(),
        'current_term': Term.get_current(),
    }
