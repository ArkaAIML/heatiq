from app.api.schemas import HTSIResult, AlertPayload

def generate_alert(htsi: HTSIResult) -> AlertPayload:
    if htsi.category == "CRITICAL":
        return AlertPayload(
            level="CRITICAL HEAT RISK",
            message="Extreme thermal stress expected.",
            action_required="Avoid outdoor exposure."
        )
    return AlertPayload(
        level="NORMAL",
        message="Conditions are safe.",
        action_required="None"
    )
