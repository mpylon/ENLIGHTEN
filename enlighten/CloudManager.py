import os
import boto3
import logging
from typing import Optional

from PySide2 import QtCore, QtWidgets, QtGui
from PySide2.QtWidgets import QInputDialog, QLineEdit, QMessageBox, QPushButton

from .common import get_default_data_dir
from .EEPROMEditor import EEPROMEditor

log = logging.getLogger(__name__)

try:
    from .keys import *
    DISABLED = False
except Exception as e:
    DISABLED = True
    log.error("No AWS keys found. Cloud eeprom restore disabled")

class CloudManager:
    """
    Encapsulates access to AWS-backed cloud features.
    """

    def __init__(self, 
                 restore_button: QPushButton, 
                 eeprom_editor: EEPROMEditor) -> None:

        if DISABLED:
            log.info("No keys, so not initializing cloud manager class")
            return
        self.restore_button = restore_button
        self.eeprom_editor = eeprom_editor

        self.result_message = QMessageBox(self.restore_button)
        self.result_message.setWindowTitle("Restore EEPROM Result")
        self.result_message.setStandardButtons(QMessageBox.Ok)

        self.restore_button.clicked.connect(self.perform_restore)

    def perform_restore(self) -> None:
        serial_number = self.prompt_for_serial()
        self.setup_connection()
        if serial_number != None:
            local_file, download_result = self.attempt_download(serial_number)
            if download_result:
                log.debug(f"succeeded in downloading cloud file {serial_number}")
                import_result = self.eeprom_editor.import_eeprom(file_name=local_file)
                if not import_result:
                    log.error("Error in eeprom editor import")
                    self.result_message.setText("EEPROM Writing Error.")
                    self.result_message.setIcon(QMessageBox.Critical)
                    self.result_message.exec_()
                self.result_message.setText("EEPROM Restore successful.")
                self.result_message.setIcon(QMessageBox.NoIcon)
                self.result_message.exec_()

    def setup_connection(self) -> None:
        self.session = self.create_session()
        self.s3_resource = self.session.resource("s3")
        self.eeprom_bucket = self.s3_resource.Bucket("eeprom-factory-files")
        log.debug("Finished setting up connection to cloud provider")

    def attempt_download(self, serial_number: str) -> tuple[str, bool]:
        local_file = ''
        try:
            local_file = os.path.join(get_default_data_dir(), "eeprom_backups", f"{serial_number}.json")
            self.eeprom_bucket.download_file(f"{serial_number}.json", local_file)
        except Exception as e:
            log.error(f"Ran into error trying to download cloud eeprom file of {e}")
            self.result_message.setText("Error retrieving EEPROM file from server.")
            self.result_message.setIcon(QMessageBox.Critical)
            self.result_message.exec_()
            return (local_file, False)
        return (local_file, True)

    def prompt_for_serial(self) -> Optional[str]:
        text, ok = QInputDialog().getText(self.restore_button, 
                                          "Enter Spectrometer Serial Number",
                                          "Serial Number",
                                          QLineEdit.Normal)
        if not ok:
            return
        
        return text

    def create_session(self) -> boto3.Session:
        client = boto3.client("cognito-identity", region_name="us-east-1")

        log.debug("getting client credentials")
        response = client.get_id(
            IdentityPoolId=ID_POOL_ID,
            )

        response_cred = client.get_credentials_for_identity(
            IdentityId=response["IdentityId"],
            )

        access_id = response_cred["Credentials"]["AccessKeyId"]
        access_secret = response_cred["Credentials"]["SecretKey"]
        access_session = response_cred["Credentials"]["SessionToken"]
        log.debug("Obtained client credentials, setting up client session")
        s3_session = boto3.Session(
            aws_access_key_id=access_id,
            aws_secret_access_key=access_secret,
            aws_session_token=access_session,
            )
        log.debug("Created client session")
        return s3_session
