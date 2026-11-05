from django.shortcuts import render

def forbidden(request, exception=None):
    return render(request, 'error.html', {'code': 403, 'heading': 'This action needs different access.', 'explanation': 'Check your organisation role and verification status, or ask the administrator for help.'}, status=403)

def not_found(request, exception=None):
    return render(request, 'error.html', {'code': 404, 'heading': 'We could not find that page.', 'explanation': 'The listing may no longer be accessible to your organisation. Return to your workspace to find current donations.'}, status=404)

def server_error(request):
    # A standalone template avoids database-dependent navigation during an outage.
    return render(request, 'server_error.html', status=500)
