# Home Assistant Integration

Gregory can interact with your Home Assistant instance to read sensor states, control lights, and call other services. This integration uses the Home Assistant REST API with a long-lived access token.

## Prerequisites

- Home Assistant running on your network (same LAN as Gregory, or reachable URL)
- A long-lived access token

## Setup

### 1. Create a Long-Lived Access Token

1. Log into your Home Assistant frontend in a browser
2. Click your profile (bottom-left)
3. Scroll to **Long-Lived Access Tokens**
4. Click **Create Token**
5. Give it a name (e.g. "Gregory") and copy the token

**Important:** Store the token securely. Do not commit it to version control.

### 2. Configure Gregory

Add these settings to `config.json` or set environment variables:

```json
{
  "ha_enabled": true,
  "ha_base_url": "http://192.168.0.x:8123",
  "ha_access_token": "your-long-lived-token-here"
}
```

Or via environment:

- `HA_ENABLED=true`
- `HA_BASE_URL=http://192.168.0.x:8123`
- `HA_ACCESS_TOKEN=your-token`

Replace `192.168.0.x` with your Home Assistant server's IP or hostname. Use `https://` if you have SSL.

### 3. Restart Gregory

Restart the Gregory server so the new config is loaded.

## Usage

When `ha_enabled` is true, Gregory receives instructions to use special markers in his responses. He will:

- **Find entities by name** — `[HA_FIND: front door]` to search by friendly name (e.g. "front door", "living room light"). Use this when the user mentions a device by name and you don't know the exact entity_id.
- **List entities** — `[HA_LIST]` or `[HA_LIST: light]` to see available entities
- **Read state** — `[HA_STATE: sensor.temperature_living_room]` to get current values
- **Call services** — `[HA_SERVICE: light.turn_on | entity_id=light.living_room]` to control devices

When you ask about something by name (e.g. "Is the front door open?"), Gregory will use `[HA_FIND: front door]` first to find the correct entity, then use `[HA_STATE]` or `[HA_SERVICE]` with that entity_id.

**Tip:** Rename entities in Home Assistant (Settings → Devices → select device → rename) to descriptive names like "Table Lamp - Master Bedroom". Gregory searches by friendly name; generic names like "Smart RGB TW Bulb 4" are harder to match.

### Example User Prompts

- "What lights do we have?"
- "Turn on the living room light"
- "Set the kitchen light to 50% brightness and warm white"
- "What's the temperature in the living room?"
- "Turn off all the lights"

## Light Control Parameters

For `light.turn_on`:

- **brightness** — 1–255 (255 = full)
- **color_temp_kelvin** — Color temperature (e.g. 2700 = warm, 6500 = cool)
- **rgb_color** — `R,G,B` each 0–255 (e.g. `255,128,0` for orange)
- **transition** — Fade duration in seconds

## Troubleshooting

### "Home Assistant unreachable"

- Check `ha_base_url` is correct and reachable from Gregory’s host
- Ensure Home Assistant is running and the API is enabled
- If using HTTPS, verify the certificate

### "Unauthorized (check access token)"

- Regenerate the token in your Home Assistant profile
- Ensure `ha_access_token` is set correctly (no extra spaces)
- Confirm the token has not expired

### "Entity X not found"

- Use `[HA_LIST: domain]` to see valid entity IDs
- Entity IDs follow `domain.name` (e.g. `light.living_room`, `sensor.temperature`)

### Command reported success but device didn't respond

- Gregory reports "Successfully called" when Home Assistant accepts the HTTP request (200)
- The device itself may be offline, on a different network, or the integration may have issues
- Check Home Assistant logs (Settings → System → Logs) for device/integration errors
- Try the same action in the Home Assistant UI to see if it works there

### Gregory doesn’t use HA markers

- Ensure `ha_enabled` is `true` and both `ha_base_url` and `ha_access_token` are set
- Restart Gregory after config changes
- Try more explicit prompts: "Use Home Assistant to turn on the living room light"
