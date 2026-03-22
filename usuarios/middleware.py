from django.shortcuts import render

class AdminAccessMiddleware:
    """
    Middleware para interceptar accesos al panel /admin/.
    Si el usuario está autenticado pero NO es staff, muestra la página 403 personalizada
    en lugar del formulario de login de Django Admin.
    """
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        if request.path.startswith('/admin/'):
            if request.user.is_authenticated and not request.user.is_staff:
                return render(request, '403.html', status=403)
        
        response = self.get_response(request)
        return response
