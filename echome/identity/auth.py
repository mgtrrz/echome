from .models import User, UserAccessAccounts

def user_authentication_rule(user):
    if isinstance(user, User):
        return False
    
    if isinstance(user, UserAccessAccounts):
        return user is not None and user.is_active

    return False