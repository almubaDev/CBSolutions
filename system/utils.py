def get_client_ip(request):
    """
    Obtiene la dirección IP del cliente que hace la petición.
    Tiene en cuenta los posibles proxies en la cadena.
    """
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0].strip()
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip