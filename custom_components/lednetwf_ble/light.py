import logging
import voluptuous as vol
from typing import Any, Optional
from .lednetwf import LEDNETWFInstance
from .const import (DOMAIN)

from homeassistant.const import CONF_MAC
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity import DeviceInfo
from homeassistant.components.light import (
    PLATFORM_SCHEMA,
    ATTR_BRIGHTNESS,
    ATTR_COLOR_TEMP_KELVIN,
    ATTR_EFFECT,
    EFFECT_OFF,
    ATTR_HS_COLOR,
    ATTR_RGB_COLOR,
    ColorMode,
    LightEntity,
    LightEntityFeature,
)
from homeassistant.helpers import device_registry

LOGGER = logging.getLogger(__name__)
PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({vol.Required(CONF_MAC): cv.string})


async def async_setup_entry(hass, config_entry, async_add_devices):
    instance = hass.data[DOMAIN][config_entry.entry_id]
    await instance.update()
    
    devices = [LEDNETWFLight(instance, config_entry.data["name"], config_entry.entry_id)]
    
    # Add background light entity only for models that support it (0x56, 0x80)
    if hasattr(instance._model_interface, 'set_bg_color') and instance.model_number in [0x56, 0x80]:
        LOGGER.info(f"Adding background light entity for model 0x{instance.model_number:02x}")
        devices.append(LEDNETWFBackgroundLight(instance, config_entry.data["name"], config_entry.entry_id))
    
    async_add_devices(devices)
    #config_entry.async_on_unload(await instance.stop())


class LEDNETWFLight(LightEntity):
    _attr_has_entity_name = False

    def __init__(
        self, lednetwfinstance: LEDNETWFInstance, name: str, entry_id: str
    ) -> None:
        self._instance = lednetwfinstance
        self._entry_id = entry_id
        self._attr_supported_color_modes = self._instance._model_interface.supported_color_modes
        self._attr_supported_features = LightEntityFeature.EFFECT
        self._attr_name               = name
        self._attr_unique_id          = self._instance.mac
        # Register this entity's callback
        self._instance.register_callback(self.light_local_callback)
        
    @property
    def available(self):
        return self._instance.is_on is not None

    @property
    def brightness(self):
        return self._instance.brightness
    @property
    def brightness_step_pct(self):
        return 10
    
    @property
    def is_on(self) -> Optional[bool]:
        return self._instance.is_on

    @property
    def color_temp_kelvin(self):
        return self._instance.color_temp_kelvin

    @property
    def max_color_temp_kelvin(self):
        return self._instance.max_color_temp_kelvin

    @property
    def min_color_temp_kelvin(self):
        return self._instance.min_color_temp_kelvin

    @property
    def effect_list(self):
        return self._instance.effect_list

    @property
    def effect(self):
        return self._instance.effect

    @property
    def supported_features(self) -> int:
        """Flag supported features."""
        return self._attr_supported_features

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        return self._attr_supported_color_modes

    @property
    def hs_color(self):
        """Return the hs color value."""
        return self._instance.hs_color
  
    @property
    def rgb_color(self):
        """Return the rgb color value."""
        return self._instance.rgb_color

    @property
    def color_mode(self):
        """Return the color mode of the light."""
        return self._instance.color_mode
    
    @property
    def firmware_version(self):
        return self._instance.firmware_version
    
    @property
    def device_info(self):
        """Return device info."""
        return DeviceInfo(
            identifiers={
            (DOMAIN, self._instance.mac)
            },
            name=self.name,
            connections={(device_registry.CONNECTION_NETWORK_MAC, self._instance.mac)},
            model=f"0x{self._instance.model_number:02x}",
            sw_version=self.firmware_version
        )

    @property
    def should_poll(self):
        return False

    @property
    def name(self) -> str:
        return self._attr_name
    
    @property
    def icon(self):
        return self._instance._model_interface.icon
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        LOGGER.debug("async_turn_on called")
        LOGGER.debug("kwargs: %s", kwargs)

        if not self.is_on:
            await self._instance.turn_on()

        on_brightness = kwargs.get(ATTR_BRIGHTNESS)
        if on_brightness is None and self._instance.brightness is not None and self._instance.brightness > 0:
            on_brightness = self._instance.brightness
        elif on_brightness is None or on_brightness == 0:
            on_brightness = 255


        if ATTR_COLOR_TEMP_KELVIN not in kwargs and ATTR_HS_COLOR not in kwargs and ATTR_EFFECT not in kwargs and ATTR_RGB_COLOR not in kwargs:
            # i.e. only a brightness change
            if self._instance.effect is not None and self._instance.effect is not EFFECT_OFF:
                # Before HA 2024.2

                # effect check go first because of the way HA handles brightness changes
                # if there is no color mode set, the brightness slider in the UI gets disabled
                # so we bodge it by keep the color mode set while adjusting the effect brightness.

                #HA 2024.2 changes this, setting color mode to "brightness" should allow to change effects brightness as well as introduces the predefined EFFECT_OFF status
                kwargs[ATTR_EFFECT] = self._instance.effect
            elif self._instance.color_mode is ColorMode.COLOR_TEMP:
                kwargs[ATTR_COLOR_TEMP_KELVIN] = self._instance.color_temp_kelvin
            elif self._instance.color_mode is ColorMode.HS:
                kwargs[ATTR_HS_COLOR] = self._instance.hs_color
            elif self._instance.color_mode is ColorMode.RGB:
                kwargs[ATTR_RGB_COLOR] = self._instance.rgb_color

        if ATTR_BRIGHTNESS in kwargs and ATTR_EFFECT == EFFECT_OFF:
            self._instance._effect = EFFECT_OFF
        
        # Set foreground color/effect
        if ATTR_COLOR_TEMP_KELVIN in kwargs:
            self._instance._color_mode = ColorMode.COLOR_TEMP
            await self._instance.set_color_temp_kelvin(kwargs[ATTR_COLOR_TEMP_KELVIN], on_brightness)
        elif ATTR_HS_COLOR in kwargs:
            # set_hs_color -> set_color includes background color in the packet
            await self._instance.set_hs_color(kwargs[ATTR_HS_COLOR], on_brightness)
        elif ATTR_RGB_COLOR in kwargs:
            await self._instance.set_rgb_color(kwargs[ATTR_RGB_COLOR], on_brightness)
        elif ATTR_EFFECT in kwargs and kwargs[ATTR_EFFECT] != EFFECT_OFF:
            effect = kwargs[ATTR_EFFECT]
            # Don't try to set unknown effects
            if effect.startswith("Unknown Effect"):
                LOGGER.warning(f"Cannot set unknown effect: {effect}. Ignoring.")
            else:
                await self._instance.set_effect(effect, on_brightness)
        
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        await self._instance.turn_off()
        self.async_write_ha_state()

    async def async_update(self) -> None:
        LOGGER.debug("async update called")
        await self._instance.update()
    
    def light_local_callback(self):
        LOGGER.debug(f"light_local_callback triggered for {self._instance._mac}")
        LOGGER.debug(f"Current state: is_on={self._instance.is_on}, brightness={self._instance.brightness}")
        self.schedule_update_ha_state()

    def update_ha_state(self) -> None:
        LOGGER.debug("update_ha_state called")
        if self.hs_color is None and self.color_temp_kelvin is None and self.rgb_color is None:
            if self._instance._effect is not None and self._instance._effect is not EFFECT_OFF:
                self._color_mode = ColorMode.BRIGHTNESS 
                #2024.2 We can use brightness color mode so even when we don't know the state of the light the brightness can be controlled
                #2025.3 ColorMode.BRIGHTNESS is not considered a valid supported color when on standalone, this gets ignored when
                #light is rendering an effect 
            else:
                self._color_mode = ColorMode.UNKNOWN
                #2025.3 When not sure of color mode ColorMode.UNKNOWN avoids throwing errors on unsupported combination of color modes
        elif self.hs_color is not None:
            self._color_mode = ColorMode.HS
        # elif self.rgb_color is not None:
        #     self._color_mode = ColorMode.RGB
        elif self.color_temp_kelvin is not None:
            self._color_mode = ColorMode.COLOR_TEMP
        self.available = self._instance.is_on is not None
        self.async_write_ha_state()


class LEDNETWFBackgroundLight(LightEntity):
    """Background light entity for devices that support background color (0x56, 0x80)."""
    _attr_has_entity_name = True

    def __init__(
        self, lednetwfinstance: LEDNETWFInstance, name: str, entry_id: str
    ) -> None:
        self._instance = lednetwfinstance
        self._entry_id = entry_id
        self._attr_supported_color_modes = {ColorMode.HS}
        self._attr_name = "Background"  # This will be the entity name suffix
        self._attr_unique_id = f"{self._instance.mac}_background"
        self._device_name = name  # Store the device name for reference
        self._is_on = True  # Track on/off state independently from brightness
        # Register this entity's callback
        self._instance.register_callback(self.bg_light_local_callback)
        
    @property
    def available(self):
        """Background light is only available for static effects (excluding Solid Color)."""
        if self._instance.is_on is None:
            return False
        
        current_effect = self._instance.effect
        
        # Only available for static effects (Static Effect 2-10)
        # NOT available for: color mode, Solid Color, dynamic effects, or sound reactive
        if current_effect is None or current_effect == EFFECT_OFF:
            return False
            
        # Static effects (but not "Solid Color" which is now EFFECT_OFF)
        return "Static Effect" in current_effect

    @property
    def brightness(self):
        return self._instance.bg_brightness
    
    @property
    def brightness_step_pct(self):
        return 10
    
    @property
    def is_on(self) -> Optional[bool]:
        # Background light has its own on/off state, independent of brightness value
        return self._instance.is_on and self._is_on

    @property
    def supported_color_modes(self) -> set[ColorMode]:
        """Flag supported color modes."""
        return self._attr_supported_color_modes

    @property
    def hs_color(self):
        """Return the hs color value."""
        return self._instance.bg_hs_color
  
    @property
    def rgb_color(self):
        """Return the rgb color value."""
        return self._instance.bg_rgb_color

    @property
    def color_mode(self):
        """Return the color mode of the light."""
        return ColorMode.HS
    
    @property
    def firmware_version(self):
        return self._instance.firmware_version
    
    @property
    def device_info(self):
        """Return device info - links to same device as main light."""
        return DeviceInfo(
            identifiers={
                (DOMAIN, self._instance.mac)
            },
            # Don't set name here - it will link to existing device with same identifiers
            connections={(device_registry.CONNECTION_NETWORK_MAC, self._instance.mac)},
            model=f"0x{self._instance.model_number:02x}",
            sw_version=self.firmware_version
        )

    @property
    def should_poll(self):
        return False

    @property
    def name(self) -> str:
        return self._attr_name
    
    @property
    def icon(self):
        return "mdi:layers-triple"
    
    async def async_turn_on(self, **kwargs: Any) -> None:
        LOGGER.debug("Background light async_turn_on called")
        LOGGER.debug("kwargs: %s", kwargs)

        # Ensure main light is on
        if not self._instance.is_on:
            await self._instance.turn_on()

        # Mark as on
        self._is_on = True

        # Determine brightness - preserve current brightness if not explicitly set
        on_brightness = kwargs.get(ATTR_BRIGHTNESS)
        if on_brightness is None:
            # If no brightness is specified, use current brightness if reasonable
            # Threshold of 10 to avoid very dim colors when turning on
            if self._instance.bg_brightness is not None and self._instance.bg_brightness >= 10:
                on_brightness = self._instance.bg_brightness
            else:
                # Check if we have a saved brightness from before turning off
                if hasattr(self, '_last_brightness') and self._last_brightness >= 10:
                    on_brightness = self._last_brightness
                    LOGGER.debug(f"Restoring last brightness: {on_brightness}")
                else:
                    # Default to full brightness when turning on from off/very dim state
                    on_brightness = 255
                    LOGGER.debug(f"Background brightness was {self._instance.bg_brightness}, defaulting to 255")

        if ATTR_HS_COLOR in kwargs:
            await self._instance.set_bg_hs_color(kwargs[ATTR_HS_COLOR], on_brightness)
        elif ATTR_RGB_COLOR in kwargs:
            # Convert RGB to HS
            from homeassistant.util.color import color_RGB_to_hs
            hs = color_RGB_to_hs(*kwargs[ATTR_RGB_COLOR])
            await self._instance.set_bg_hs_color(hs, on_brightness)
        else:
            # Just turning on or brightness change - preserve color
            await self._instance.set_bg_hs_color(self._instance.bg_hs_color, on_brightness)
        
        self.async_write_ha_state()

    async def async_turn_off(self, **kwargs: Any) -> None:
        # Save current brightness before turning off (if it's reasonable)
        if self._instance.bg_brightness >= 10:
            self._last_brightness = self._instance.bg_brightness
            LOGGER.debug(f"Saving brightness {self._last_brightness} before turn off")
        
        # Mark as off and set background to black (brightness 0)
        self._is_on = False
        await self._instance.set_bg_hs_color(self._instance.bg_hs_color, 0)
        self.async_write_ha_state()

    async def async_update(self) -> None:
        LOGGER.debug("Background light async_update called")
        await self._instance.update()
        self.async_write_ha_state()
    
    def bg_light_local_callback(self):
        """Called when device state changes via notification."""
        self.async_write_ha_state()
