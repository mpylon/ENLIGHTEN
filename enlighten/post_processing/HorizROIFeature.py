import logging

from wasatch.ProcessedReading import ProcessedReading

log = logging.getLogger(__name__)

class HorizROIFeature:
    """
    Encapsulate the Horizontal ROI feature.

    @par Persistance

    The result of HorizROI processing is stored in the given ProcessedReading,
    by storing cropped versions of that PR's key arrays (proc/raw/dark/ref/wl/wn)
    in a new .cropped ProcessedReading.

    @par Order of Operations

    This should be called BEFORE Interpolation, and most everything else.
    @see ORDER_OF_OPERATIONS.md

    @par Enabling and Visualization
    
    It is very important to understand what it means for this feature to be 
    "enabled," and how that is visualized.
    
    Wasatch has gone back and forth a couple times on whether this feature
    should default to enabled (only show GOOD data to avoid confusing users)
    or disabled (show all raw data to scientists). 

    The current behavior is to default ENABLED (the cropped spectrum is shown) 
    if a horizontal ROI is configured in the spectrometer's EEPROM.

    The colorization of this button may seem a little non-intuitive in comparison
    to other ENLIGHTEN features, but actually it's consistent "...from a certain
    point of view."

    Normally ENLIGHTEN colors buttons red when they have been clicked (changed
    from their "default" state), and particularly if they are in a "dangerous/
    hazardous" mode (laser firing, unusual transformations applied etc).

    That is arguably the case here. The button is grey when in a "safe, happy"
    state (ROI enabled and showing good data), and red when in an unusual "risky"
    state (ROI disabled and showing invalid data).

    (One could argue that by that logic, the DarkCorrection button should be
    red when dark is NOT applied, i.e. in a dangerous state...hmm.)
    
    If a horizontal ROI is configured, the BUTTON is ENABLED (clickable); if no
    ROI is configured, the button is DISABLED (not clickable). In either case, a
    ToolTip explains the current status.

    If the user clicks the button and DISABLES the Horiz ROI, what will happen 
    depends on whether the user is in Expert Mode or not.

    @verbatim
                    ROI in EEPROM           No ROI in EEPROM
    At launch:      - button enabled        - button disabled
                    - button on (grey)      - button off (grey)
                    - ToolTip "click to     - ToolTip "no horiz ROI"
                      disable horiz ROI"
    @endverbatim
    """
    
    def __init__(self, ctl):
        self.ctl = ctl

        self.button = self.ctl.form.ui.pushButton_roi_toggle 
        self.cb_editing = self.ctl.form.ui.checkBox_edit_horiz_roi

        log.debug("init: defaulting to enabled and user_requested_enabled (i.e. grey)")
        self.enabled = True
        self.user_requested_enabled = True

        self.observers = set()
        self.ctl.graph.register_observer("change_axis", self.change_axis_callback)

        self.button.clicked.connect(self.button_callback)
        self.cb_editing.stateChanged.connect(self.cb_editing_callback)

        self.update_visibility()

    def change_axis_callback(self, old_axis_enum, new_axis_enum):
        self.update_regions()

    def button_callback(self):
        self.enabled = not self.enabled
        self.user_requested_enabled = self.enabled

        log.debug(f"button_callback: user_requested_enabled = {self.user_requested_enabled}, enabled = {self.enabled}")
        
        self.update_visibility()

    def cb_editing_callback(self):
        for spec in self.ctl.multispec.get_spectrometers():
            self.update_regions(spec)

    ## provided for RichardsonLucy to flush its Gaussian cache
    def register_observer(self, callback):
        self.observers.add(callback)

    def init_hotplug(self):
        """ auto-enable for spectrometers with ROI """
        spec = self.ctl.multispec.current_spectrometer()
        self.enabled = spec is not None and spec.settings.eeprom.has_horizontal_roi() and self.user_requested_enabled
        log.debug(f"init_hotplug: enabled = {self.enabled}")

    def update_visibility(self):
        spec = self.ctl.multispec.current_spectrometer()
        if spec is None:
            return

        self.cb_editing.setVisible(self.ctl.page_nav.doing_expert())

        log.debug(f"update_visibility: setting enabled to user_requested_enabled {self.user_requested_enabled}")
        self.enabled = self.user_requested_enabled

        if spec is not None and spec.settings.eeprom.has_horizontal_roi():
            log.debug(f"update_visibility: showing because spec and ROI")
            self.button.setVisible(True)

            if self.enabled:
                self.ctl.stylesheets.apply(self.button, "gray_gradient_button") 
                self.button.setToolTip("spectra cropped per horizontal ROI")
            else:
                self.ctl.stylesheets.apply(self.button, "red_gradient_button")
                self.button.setToolTip("uncropped spectra shown (curtains indicate ROI limits)")

        else:
            log.debug(f"update_visibility: hiding because no spec or no ROI")
            if spec:
                log.debug(f"update_visibility: roi = {spec.settings.eeprom.get_horizontal_roi()}")
            self.button.setVisible(False)
            self.enabled = False

        log.debug(f"update_visibility: user_requested_enabled = {self.user_requested_enabled}, enabled = {self.enabled}")

        for spec in self.ctl.multispec.get_spectrometers():
            self.update_regions(spec)

        for callback in self.observers:
            callback()

    def is_editing(self):
        return self.cb_editing.isChecked()

    def crop(self, spectrum, spec=None, roi=None, settings=None):
        """
        We are trying to get fewer classes to call this, in preference of using the 
        .cropped attribute stored in the original ProcessedReading.

        Note this can be used for any array, not just spectra.
        """
        if spectrum is None:
            return

        # we need an ROI
        if roi is None and settings:
            roi = spec.settings.eeprom.get_horizontal_roi()
        if roi is None and spec:
            roi = spec.settings.eeprom.get_horizontal_roi()
        if roi is None:
            spec = self.ctl.multispec.current_spectrometer()
            if spec:
                roi = spec.settings.eeprom.get_horizontal_roi()
        if roi is None:
            return spectrum

        orig_len = len(spectrum)
        if not roi.valid() or roi.start >= orig_len or roi.end >= orig_len:
            return spectrum

        # log.debug("crop: cropping spectrum of %d pixels to %d (%s)", orig_len, roi.len, roi)
        return roi.crop(spectrum)
        
    ##
    # Called by Controller.process_reading.
    # 
    # @param pr (In/Out) ProcessedReading
    # @param settings (Input) SpectrometerSettings
    #
    # @returns Nothing (side-effect: populates pr.cropped)
    def process(self, pr, settings=None):
        if not self.enabled:
            return

        if pr is None or pr.processed is None:
            return

        if settings is None:
            settings = pr.settings
        if settings is None:
            spec = self.ctl.multispec.current_spectrometer()
            if spec is not None:
                settings = spec.settings
        if settings is None:
            return

        roi = settings.eeprom.get_horizontal_roi()
        if roi is None:
            return 
            
        prc = ProcessedReading(settings=settings)
        prc.processed   = self.crop(pr.processed,         roi=roi)
        prc.raw         = self.crop(pr.raw,               roi=roi)
        prc.reference   = self.crop(pr.raw,               roi=roi)
        prc.wavelengths = self.crop(settings.wavelengths, roi=roi)
        prc.wavenumbers = self.crop(settings.wavenumbers, roi=roi)

        pr.cropped = prc

    def update_regions(self, spec=None):
        if spec is None:
            spec = self.ctl.multispec.current_spectrometer()
        if spec is None:
            return

        # only show the curtains if we're editing the ROI
        if not self.is_editing():
            self.ctl.graph.remove_roi_region(spec.roi_region_left)
            self.ctl.graph.remove_roi_region(spec.roi_region_right)
            return

        roi = spec.settings.eeprom.get_horizontal_roi()
        if roi:
            start = roi.start
            end = roi.end
        else:
            start = 0
            end = spec.settings.pixels()

        axis = self.ctl.generate_x_axis(cropped=False)

        log.debug(f"update_regions: roi {roi}, axis {len(axis)} elements, start {start}, end {end}")

        spec.roi_region_left.setRegion((axis[0], axis[start]))
        spec.roi_region_right.setRegion((axis[end], axis[-1]))

        # automatically make regions invisible if they actually extend to/past 
        # the detector edge
        #
        # MZ: how is setOpacity(0) different from remote_roi_region()?
        #     why are we ADDING an opaque region, if I'm reading this
        #     right?
        #
        # MZ: disabling this for now until I understand what it was for.
        #
        # if roi.start <= 0:
        #     spec.roi_region_left.setOpacity(0)
        # else:
        #     spec.roi_region_left.setOpacity(1)
        # 
        # if roi.end >= len(axis):
        #     spec.roi_region_right.setOpacity(0)
        # else:
        #     spec.roi_region_right.setOpacity(1)

        self.ctl.graph.add_roi_region(spec.roi_region_left)
        self.ctl.graph.add_roi_region(spec.roi_region_right)
