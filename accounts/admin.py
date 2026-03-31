from django import forms
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from .models import User, Role


class CustomUserChangeForm(forms.ModelForm):
    class Meta:
        model = User
        fields = '__all__'

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Staff roles only — no Student or Parent for staff accounts
        if self.instance and self.instance.is_superuser:
            self.fields['roles'].queryset = Role.objects.exclude(
                name__in=['STUDENT', 'PARENT']
            )


@admin.register(Role)
class RoleAdmin(admin.ModelAdmin):
    list_display = ['name']


@admin.register(User)
class CustomUserAdmin(UserAdmin):
    form = CustomUserChangeForm
    list_display = [
        'username', 'get_full_name',
        'email', 'get_roles', 'is_active'
    ]
    list_filter = ['roles', 'is_active']
    filter_horizontal = ['roles']

    fieldsets = UserAdmin.fieldsets + (
        ('School Info', {
            'fields': (
                'roles', 'phone_number',
                'profile_picture', 'is_first_login'
            )
        }),
    )

    def get_roles(self, obj):
        return obj.get_role_display() or 'No roles'
    get_roles.short_description = 'Roles'