#!/usr/bin/python
# -*- coding: utf-8 -*-

from functools import partial

from PyQt5.QtWidgets import QWidget, QSpinBox, QCheckBox, QPushButton, \
    QGroupBox, QFormLayout, QLabel, QVBoxLayout, QSizePolicy, QHBoxLayout, QFileDialog
from PyQt5.QtCore import pyqtSignal

from .helpers import CollapseBox
from .biases import get_biases_from_file


class MetavisionWidget(QWidget):
    """
    Simple Widget to handle Metavision Cameras
    """
    # Biases Signals
    biases_reset = pyqtSignal()  # emitted when bias reset button clicked
    biases_save = pyqtSignal()  # emitted when bias save button clicked
    bias_changed = pyqtSignal(str, int)  # emit bias name,value when changed in widget

    # ROI Signals
    roi_reset = pyqtSignal()  # emitted when roi reset button clicked
    roi_save = pyqtSignal()  # emitted when roi save button clicked
    roi_changed = pyqtSignal()  # emitted whenever roi changed.

    # ERC signal
    erc_changed = pyqtSignal(int)  # emitted when cd_target_rate is updated
    erc_enabled = pyqtSignal(int)  # emitted when check box of erc enable change

    # STC/TRAIL
    stc_enabled = pyqtSignal(int)
    trail_enabled = pyqtSignal(int)
    noise_filter_disabled = pyqtSignal()

    # AFK
    afk_freq_changed = pyqtSignal(int, int)  # emitted when afk min/max frequency is updated
    afk_enabled = pyqtSignal(bool)  # emitted when afk_enable is toggled

    # fps signal
    fps_changed = pyqtSignal(int)  # emitted when display rate is changed

    # record signal
    record_toggled = pyqtSignal(bool)  # emitted when record is toggled

    # close signal
    close_clicked = pyqtSignal()  # emitted when close button clicked

    def __init__(self, serial_id: str, biases={}, hw_major_version=3, hw_minor_version=1,
                 is_live_camera=False,
                 erc_cd_target=20000000,
                 erc_enabled=False,
                 fps=25,
                 parent=None):
        super().__init__(parent)

        # Setup bias
        self.biases_spinbox = {}
        self.bias_group = None
        self.bias_notify = True
        if biases:
            bias_step = 5
            bias_min = 0
            bias_max = 1800
            if hw_major_version == 4:
                bias_step = 1
                bias_max = 255

            bias_group = CollapseBox('Bias setters')
            bias_layout = QFormLayout()

            # One spinbox per bias
            for name, value in biases.items():
                spinbox = QSpinBox()
                spinbox.setRange(bias_min, bias_max)
                spinbox.setSingleStep(bias_step)
                spinbox.setKeyboardTracking(False)
                spinbox.setValue(value)
                spinbox.valueChanged[int].connect(partial(self.on_bias_change, name))
                bias_layout.addRow(name, spinbox)
                self.biases_spinbox[name] = spinbox

            # Reset button
            bias_reset_btn = QPushButton("Reset")
            bias_reset_btn.clicked.connect(self.biases_reset.emit)

            # Load button
            bias_load_btn = QPushButton("Load")
            bias_load_btn.clicked.connect(self.on_biases_load)

            # Save button
            bias_save_btn = QPushButton("Save")
            bias_save_btn.clicked.connect(self.biases_save.emit)

            bias_buttons_layout = QHBoxLayout()
            bias_buttons_layout.addWidget(bias_reset_btn)
            bias_buttons_layout.addWidget(bias_load_btn)
            bias_buttons_layout.addWidget(bias_save_btn)
            bias_layout.addRow(bias_buttons_layout)

            # Layout
            bias_group.setContentLayout(bias_layout)
            bias_group.setCollapsed(False)
            self.bias_group = bias_group

        # Setup ROI
        self.roi_spinbox = {}
        self.roi_group = None
        if is_live_camera:
            # value, min, max tuple
            roi_dict = {'x': (0, 0, 639), 'y': (0, 0, 479), 'width': (640, 1, 640), 'height': (480, 1, 480)}
            if hw_major_version == 4:
                roi_dict['x'] = (0, 0, 1279)
                roi_dict['y'] = (0, 0, 719)
                roi_dict['width'] = (1280, 1, 1280)
                roi_dict['height'] = (720, 1, 720)

            roi_group = CollapseBox('ROI setters')
            roi_layout = QFormLayout()

            # One spinbox per bias
            for name, (roi_val, roi_min, roi_max) in roi_dict.items():
                spinbox = QSpinBox()
                spinbox.setRange(roi_min, roi_max)
                spinbox.setSingleStep(1)
                spinbox.setKeyboardTracking(False)
                spinbox.setValue(roi_val)
                spinbox.valueChanged[int].connect(self.roi_changed.emit)
                roi_layout.addRow(name, spinbox)
                self.roi_spinbox[name] = spinbox

            # Reset button
            roi_reset_btn = QPushButton("Reset")
            roi_reset_btn.clicked.connect(self.roi_reset.emit)

            # Load button
            roi_load_btn = QPushButton("Load")
            roi_load_btn.clicked.connect(self.on_roi_load)

            # Save button
            roi_save_btn = QPushButton("Save")
            roi_save_btn.clicked.connect(self.roi_save.emit)

            roi_buttons_layout = QHBoxLayout()
            roi_buttons_layout.addWidget(roi_reset_btn)
            roi_buttons_layout.addWidget(roi_load_btn)
            roi_buttons_layout.addWidget(roi_save_btn)
            roi_layout.addRow(roi_buttons_layout)

            # Layout
            roi_group.setContentLayout(roi_layout)
            roi_group.setCollapsed(False)
            self.roi_group = roi_group

        self.erc_spinbox = None
        self.erc_group = None
        if is_live_camera and hw_major_version == 4:
            erc_group = CollapseBox('Event Rate Control')
            erc_layout = QFormLayout()

            spinbox = QSpinBox()
            spinbox.setRange(300, 0x7FFFFFF)
            spinbox.setSingleStep(100)
            spinbox.setValue(erc_cd_target)
            spinbox.setKeyboardTracking(False)
            erc_layout.addRow('CD target', spinbox)
            spinbox.valueChanged[int].connect(lambda rate: self.erc_changed.emit(rate))
            self.erc_spinbox = spinbox

            checkbox = QCheckBox()
            checkbox.setChecked(erc_enabled)
            checkbox.stateChanged.connect(lambda x: self.erc_enabled.emit(x))
            erc_layout.addRow('Enable', checkbox)

            erc_group.setContentLayout(erc_layout)
            erc_group.setCollapsed(False)
            self.erc_group = erc_group

        # setup AFK
        self.afk_group = None
        if is_live_camera and hw_major_version == 4 and hw_minor_version == 1:
            afk_group = CollapseBox('AFK Control')
            afk_layout = QFormLayout()

            afk_min_spinbox = QSpinBox()
            afk_min_spinbox.setRange(50, 500)
            afk_min_spinbox.setSingleStep(1)
            afk_min_spinbox.setValue(50)
            afk_min_spinbox.setKeyboardTracking(False)
            afk_min_spinbox.valueChanged[int].connect(self.on_afk_freq_changed)
            afk_max_spinbox = QSpinBox()
            afk_max_spinbox.setRange(50, 500)
            afk_max_spinbox.setSingleStep(1)
            afk_max_spinbox.setValue(500)
            afk_max_spinbox.setKeyboardTracking(False)
            afk_max_spinbox.valueChanged[int].connect(self.on_afk_freq_changed)
            afk_enabled_checkbox = QCheckBox()
            afk_enabled_checkbox.stateChanged.connect(lambda state: self.afk_enabled.emit(state))
            afk_layout.addRow('Min Freq', afk_min_spinbox)
            afk_layout.addRow('Max Freq', afk_max_spinbox)
            afk_layout.addRow('Enable', afk_enabled_checkbox)
            self.afk_min_spinbox = afk_min_spinbox
            self.afk_max_spinbox = afk_max_spinbox
            self.afk_enabled_checkbox = afk_enabled_checkbox

            afk_group.setContentLayout(afk_layout)
            afk_group.setCollapsed(False)
            self.afk_group = afk_group

        # setup noisefilter
        self.noisefilter_group = None
        if is_live_camera and hw_major_version == 4 and hw_minor_version == 1:
            noisefilter_group = CollapseBox("NoiseFilter Control")
            noisefilter_layout = QFormLayout()

            noisefilter_threshold_spinbox = QSpinBox()
            noisefilter_threshold_spinbox.setRange(1, 100)
            noisefilter_threshold_spinbox.setSingleStep(1)
            noisefilter_threshold_spinbox.setValue(10)
            noisefilter_threshold_spinbox.setKeyboardTracking(False)
            noisefilter_threshold_spinbox.valueChanged.connect(self.on_nf_threshold_changed)
            stc_enabled = QCheckBox()
            stc_enabled.stateChanged.connect(self.on_nf_stc_state_changed)
            trail_enabled = QCheckBox()
            trail_enabled.stateChanged.connect(self.on_nf_trail_state_changed)
            noisefilter_layout.addRow('Threshold (ms)', noisefilter_threshold_spinbox)
            noisefilter_layout.addRow('Enable STC', stc_enabled)
            noisefilter_layout.addRow('Enable TRAIL', trail_enabled)
            self.nf_stc_enabled = stc_enabled
            self.nf_trail_enabled = trail_enabled
            self.nf_threshold_spinbox = noisefilter_threshold_spinbox

            noisefilter_group.setContentLayout(noisefilter_layout)
            noisefilter_group.setCollapsed(False)
            self.noisefilter_group = noisefilter_group

        # Setup Frame Rate & Acc time
        gui_group = QGroupBox('Display parameters')
        gui_layout = QFormLayout()

        fps_spinbox = QSpinBox()
        fps_spinbox.setRange(1, 100)
        fps_spinbox.setValue(fps)
        fps_spinbox.setSingleStep(1)
        fps_spinbox.valueChanged[int].connect(self.fps_changed.emit)
        gui_layout.addRow('Display rate (fps)', fps_spinbox)
        gui_group.setLayout(gui_layout)

        # Setup metrics display
        metrics_group = CollapseBox('Device %s Metrics' % serial_id)
        self.event_rate_label = None
        self.temperature_label = None
        self.illumination_label = None
        if metrics_group:
            metrics_layout = QFormLayout()

            # Event rate
            self.event_rate_label = QLabel()
            metrics_layout.addRow('CD event rate: ', self.event_rate_label)
            self.set_event_rate(0)

            if is_live_camera:
                # Temperature rate
                self.temperature_label = QLabel()
                metrics_layout.addRow('Temperature: ', self.temperature_label)
                self.set_temperature(0)

                # Illumination
                self.illumination_label = QLabel()
                metrics_layout.addRow('Illumination: ', self.illumination_label)
                self.set_illumination(0)

            # Layout
            metrics_group.setContentLayout(metrics_layout)
            metrics_group.setCollapsed(False)

        control_group = QGroupBox('Device Control')
        control_group.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        control_layout = QVBoxLayout()

        record_state = QLabel('Not recording')
        record_state.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Fixed)
        record_state.setStyleSheet('background-color: red')
        control_layout.addWidget(record_state)
        self.record_state = record_state

        record_btn = QPushButton('Record')
        record_btn.setCheckable(True)
        record_btn.toggled.connect(self.on_record)
        self.record_btn = record_btn

        close_btn = QPushButton('Close')
        close_btn.clicked.connect(self.close_clicked.emit)

        record_close_layout = QHBoxLayout()
        record_close_layout.addWidget(record_btn)
        record_close_layout.addWidget(close_btn)
        control_layout.addLayout(record_close_layout)
        control_group.setLayout(control_layout)

        # Layout widget in 3 frames
        main_layout = QHBoxLayout()
        if is_live_camera:
            sensor_array_group = QGroupBox('Sensor Array Settings')
            sensor_array_layout = QVBoxLayout()
            sensor_array_layout.addWidget(self.bias_group)
            sensor_array_layout.addWidget(self.roi_group)
            sensor_array_group.setLayout(sensor_array_layout)
            main_layout.addWidget(sensor_array_group)

        if self.erc_group:
            sensor_esp_group = QGroupBox('Sensor ESP Settings')
            sensor_esp_layout = QVBoxLayout()
            if self.afk_group:
                sensor_esp_layout.addWidget(self.afk_group)
            if self.noisefilter_group:
                sensor_esp_layout.addWidget(self.noisefilter_group)
            sensor_esp_layout.addWidget(self.erc_group)
            sensor_esp_group.setLayout(sensor_esp_layout)
            main_layout.addWidget(sensor_esp_group)

        application_group = QGroupBox('Application Control')
        application_layout = QVBoxLayout()
        application_layout.addWidget(gui_group)
        application_layout.addWidget(metrics_group)
        application_layout.addWidget(control_group)
        application_group.setLayout(application_layout)
        main_layout.addWidget(application_group)

        self.setLayout(main_layout)

        self.setSizePolicy(QSizePolicy.Minimum, QSizePolicy.Minimum)
        self.record_btn.setFocus()

    def set_all_biases(self, biases: dict):
        for name, value in biases.items():
            if name in self.biases_spinbox:
                self.biases_spinbox[name].setValue(value)

    def fix_biases(self, biases: dict):
        self.bias_notify = False
        for name, value in biases.items():
            if name in self.biases_spinbox:
                self.biases_spinbox[name].setValue(value)
        self.bias_notify = True

    def get_all_biases(self):
        bias_dict = {}
        for bias in self.biases_spinbox:
            bias_dict[bias] = self.biases_spinbox[bias].value()

        return bias_dict

    def set_window(self, roi: dict):
        for key in roi:
            if key in self.roi_spinbox:
                self.roi_spinbox[key].setValue(roi[key])

    def get_roi(self):
        roi_dict = {}
        for key in self.roi_spinbox:
            roi_dict[key] = self.roi_spinbox[key].value()

        return roi_dict

    def set_event_rate(self, kev_per_s: float):
        if self.event_rate_label:
            if kev_per_s < 1000:
                self.event_rate_label.setText("%.1f kEv/s" % kev_per_s)
            else:
                self.event_rate_label.setText("%.2f MEv/s" % (0.001 * kev_per_s))

    def set_temperature(self, temperature: float):
        if self.temperature_label:
            self.temperature_label.setText("%.1f" % temperature)

    def set_illumination(self, illumination: int):
        if self.illumination_label:
            self.illumination_label.setText("%d" % illumination)

    def on_bias_change(self, name: str, value: int):
        if self.bias_notify:
            self.bias_changed.emit(name, value)

    def on_biases_load(self):
        bias_file, _ = QFileDialog.getOpenFileName(parent=self,
                                                   caption='Open bias file',
                                                   filter='Bias file (*.bias)')

        biases = get_biases_from_file(bias_file)
        self.set_all_biases(biases)

    def on_roi_load(self):
        roi_file_path, _ = QFileDialog.getOpenFileName(parent=self,
                                                       caption='Open ROI conf file',
                                                       filter='ROI conf file (*.conf)')
        input_roi = {}
        roi_file = open(roi_file_path, "r")
        split_line = roi_file.readline().split(" ")
        if len(split_line) == 4:
            input_roi['x'] = int(split_line[0])
            input_roi['y'] = int(split_line[1])
            input_roi['width'] = int(split_line[2])
            input_roi['height'] = int(split_line[3])

        self.set_window(input_roi)

    def on_afk_freq_changed(self, afk_freq: int):
        self.afk_freq_changed.emit(self.afk_min_spinbox.value(), self.afk_max_spinbox.value())

    def on_nf_threshold_changed(self):
        if self.nf_stc_enabled.isChecked():
            self.stc_enabled.emit(self.nf_threshold_spinbox.value() * 1000)
        elif self.nf_trail_enabled.isChecked():
            self.trail_enabled.emit(self.nf_threshold_spinbox.value() * 1000)

    def on_nf_stc_state_changed(self, stc_state: bool):
        # stc and trail can't be activated at same time
        if stc_state:
            # first check if trail enabled
            if self.nf_trail_enabled.isChecked():
                self.nf_trail_enabled.blockSignals(True)
                self.nf_trail_enabled.toggle()
                self.nf_trail_enabled.blockSignals(False)
            self.stc_enabled.emit(self.nf_threshold_spinbox.value() * 1000)
        else:
            self.noise_filter_disabled.emit()

    def on_nf_trail_state_changed(self, trail_state: bool):
        # stc and trail can't be activated at same time
        if trail_state:
            # first check if trail enabled
            if self.nf_stc_enabled.isChecked():
                self.nf_stc_enabled.blockSignals(True)
                self.nf_stc_enabled.toggle()
                self.nf_stc_enabled.blockSignals(False)
            self.trail_enabled.emit(self.nf_threshold_spinbox.value() * 1000)
        else:
            self.noise_filter_disabled.emit()

    def toggle_record(self):
        self.record_btn.setChecked(not self.record_btn.isChecked())

    def on_record(self, checked: bool):
        self.record_toggled.emit(checked)

        # Recording
        if checked:
            self.record_state.setText('recording')
            self.record_state.setStyleSheet('background-color: lightgreen')
            if self.bias_group:
                self.bias_group.setDisabled(True)

        else:
            self.record_state.setText('Not recording')
            self.record_state.setStyleSheet('background-color: red')
            if self.bias_group:
                self.bias_group.setDisabled(False)
