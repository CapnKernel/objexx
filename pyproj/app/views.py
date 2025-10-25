from django.shortcuts import render


def inventory_dashboard(request):
    """Main inventory management dashboard"""
    return render(request, 'app/dash.html')
