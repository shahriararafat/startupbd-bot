import discord

def is_authorized(interaction: discord.Interaction) -> bool:
    """Checks if the user has admin permissions or is in the custom permissions list."""
    
    # Check 1: User has 'administrator' permissions in the server.
    if interaction.user.guild_permissions.administrator:
        return True
    
    # Check 2: User's ID is in the custom 'allowed_users' list.
    if interaction.user.id in interaction.client.permissions["allowed_users"]:
        return True
    
    # Check 3: User has a role that is in the custom 'allowed_roles' list.
    user_role_ids = {role.id for role in interaction.user.roles}
    allowed_roles = set(interaction.client.permissions["allowed_roles"])
    if not user_role_ids.isdisjoint(allowed_roles):
        return True
    
    # If none of the checks pass, return False.
    return False
