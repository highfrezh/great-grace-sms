from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Role


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name', 'get_name_display']


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    list_display = [
        'username', 'get_full_name', 'email',
        'get_roles', 'is_active'
    ]
    list_filter = ['roles', 'is_active']
    filter_horizontal = ['roles']

    fieldsets = UserAdmin.fieldsets + (
        ('School Info', {
            'fields': ('roles', 'phone_number', 'profile_picture', 'is_first_login')
        }),
    )

    def get_roles(self, obj):
        return obj.get_role_display()
    get_roles.short_description = 'Roles'