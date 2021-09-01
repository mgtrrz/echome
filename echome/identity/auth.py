from .models import User

def user_authentication_rule(user):
    # JWT (API) logins should only come from the Acess Key or Service user type.
    if isinstance(user, User):
        return user is not None and user.is_active and ( user.type == User.Type.SERVICE or user.type == User.Type.ACCESS_KEY )

    return False