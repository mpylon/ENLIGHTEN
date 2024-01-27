import logging
from datetime import datetime, timedelta

from wasatch.TakeOneRequest import TakeOneRequest

log = logging.getLogger(__name__)

##
# This class encapsulates the "Raman Mode" features intended for the new 
# ramanMicro (SiG) spectrometers.  Note that HW features are developmental, so
# some are currently implemented in software; this may change as FW develops.
#
# If and when other spectrometers receive a Laser Watchdog feature, we may break
# that and other portions out into other classes.
#
# This feature cannot be enabled at startup for safety reasons.
#
# @todo consider if and where we should disable the laser if battery too low
class RamanModeFeature(object):

    LASER_WARMUP_MS = 5000
    SECTION = "Raman Mode"
    LASER_CONTROL_DISABLE_REASON = "Raman Mode enabled"

    def __init__(self, ctl):
        self.ctl = ctl
        sfu = self.ctl.form.ui

        self.bt_laser  = sfu.pushButton_laser_toggle
        self.cb_enable = sfu.checkBox_raman_mode_enable

        self.enabled = False
        self.visible = False

        self.ctl.vcr_controls.register_observer("pause", self.update_visibility)
        self.ctl.vcr_controls.register_observer("play",  self.update_visibility)

        self.cb_enable.clicked.connect(self.enable_callback)

        self.update_visibility()

        self.ctl.take_one.register_observer("start", self.take_one_start)
        self.ctl.take_one.register_observer("complete", self.take_one_complete)

    ##
    # called by Controller.disconnect_device to ensure we turn this off between
    # connections
    def disconnect(self):
        self.cb_enable.setChecked(False)
        self.update_visibility()

    ############################################################################
    # Methods
    ############################################################################

    def update_visibility(self):
        spec = self.ctl.multispec.current_spectrometer()
        if spec is None:
            self.visible = False
            is_micro = False
        else:
            is_micro = spec.settings.is_micro()
            self.visible = is_micro and \
                           self.ctl.page_nav.doing_raman() and \
                           self.ctl.vcr_controls.is_paused() and \
                           spec.settings.eeprom.has_laser

        # log.debug("visible = %s", self.visible)
        self.cb_enable.setVisible(self.visible)

        if not self.visible:
            self.cb_enable.setChecked(False)
            self.ctl.laser_control.clear_restriction(self.LASER_CONTROL_DISABLE_REASON)
        else:
            self.enable_callback()

    def generate_take_one_request(self):
        return TakeOneRequest(take_dark=True, enable_laser_before=True, disable_laser_after=True, laser_warmup_ms=3000)

    ############################################################################
    # Callbacks
    ############################################################################

    def take_one_start(self):
        log.debug(f"take_one_start: enabled {self.enabled}")
        if self.enabled:
            self.ctl.dark_feature.clear(quiet=True)
            buffer_ms = 2000
            scans_to_average = self.ctl.scan_averaging.get_scans_to_average()
            for spec in self.ctl.multispec.get_spectrometers():
                timeout_ms = buffer_ms + self.LASER_WARMUP_MS + 2 * spec.settings.state.integration_time_ms * scans_to_average
                ignore_until = datetime.now() + timedelta(milliseconds=timeout_ms)
                log.debug(f"take_one_start: setting {spec} ignore_timeouts_util = {ignore_until} ({timeout_ms} ms)")
                spec.settings.state.ignore_timeouts_until = ignore_until

            log.debug("take_one_start: forcing laser button")
            self.ctl.laser_control.refresh_laser_buttons(force_on=True)

    def take_one_complete(self):
        log.debug("take_one_complete: refreshing laser button")
        self.ctl.laser_control.refresh_laser_buttons()

    def enable_callback(self):
        enabled = self.visible and self.cb_enable.isChecked()
        log.debug("enable_callback: enable = %s", enabled)

        if enabled and not self.confirm():
            self.cb_enable.setChecked(False)
            log.debug("enable_callback: user declined (returning)")
            return

        log.debug(f"enable_callback: either we're disabling the feature (enabled {enabled}) or user confirmed okay")
        self.enabled = enabled
        if enabled:
            self.ctl.laser_control.set_restriction(self.LASER_CONTROL_DISABLE_REASON)
        else:
            self.ctl.laser_control.clear_restriction(self.LASER_CONTROL_DISABLE_REASON)
        log.debug("enable_callback: done")

    def confirm(self):
        log.debug("confirm: start")
        option = "suppress_raman_mode_warning"

        if self.ctl.config.get(self.SECTION, option, default=False):
            log.debug("confirm: user already confirmed and disabled future warnings")
            return True

        # Prompt the user. Make it scary.
        result = self.ctl.gui.msgbox_with_checkbox(
            title="Raman Mode Warning", 
            text="Raman Mode will AUTOMATICALLY FIRE THE LASER when taking measurements " + \
                 "using the ⏯ button. Be aware that the laser will automtically enable " + \
                 "and disable when taking spectra while this mode is enabled.",
            checkbox_text="Don't show again")

        if not result["ok"]:
            log.debug("confirm: user declined")
            return False

        if result["checked"]:
            log.debug("confirm: saving approval")
            self.ctl.config.set(self.SECTION, option, True)
        log.debug("confirm: returning True")
        return True