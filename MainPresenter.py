from network_scan.CoreModel import CoreModel
from address_generation.Parser import Parser
from threading import RLock
import datetime
from PyQt5.Qt import QThread, pyqtSignal
from PyQt5.QtCore import QObject, pyqtSlot
from address_generation.IpGenerator import IpGenerator
from storage.JSONStorage import JSONStorage


class MainPresenter:
    def __init__(self, ui):
        self.ui = ui
        self.threads = []
        self.isScanEnabled = False
        self.parser = Parser()
        #needed config to specify path
        self.storage = JSONStorage("results.json")
        self.exit_lock = RLock()

    def startScan(self, ipRanges, portsStr, threadNumber, timeout):
        timeout = 3 if not timeout else int(timeout)
        addresses = self.parser.parse_address_field(ipRanges)
        ports = self.parser.parse_port_field(portsStr)
        self.ip_generator = IpGenerator(addresses, ports)
        self.scanner = CoreModel(timeout)
        threadNumber = int(threadNumber)
        for i in range(threadNumber):
            scan_worker = ScanWorker(
                self.ip_generator,
                self.scanner,
                self.storage
                )
            scan_thread = QThread()
            scan_worker.log_signal.connect(self.log_text)
            scan_worker.moveToThread(scan_thread)
            scan_worker.exit_signal.connect(scan_thread.exit)
            scan_worker.exit_signal.connect(self.on_worker_exit)
            scan_thread.started.connect(scan_worker.work)
            self.threads.append((scan_worker, scan_thread))
        self.changeThreadLabel(threadNumber)
        for thread in self.threads:
            scan_worker, scan_thread = thread
            scan_thread.start()

    def changeThreadLabel(self, number_of_threads):
        self.number_of_threads = number_of_threads
        self.ui.currentThreadsLabel.setText(str(number_of_threads))

    def on_worker_exit(self):
        self.changeThreadLabel(self.number_of_threads - 1)
        with self.exit_lock:
            for num, thread in enumerate(self.threads):
                    scan_worker, scan_thread = thread
                    if not scan_worker.isRunning:
                        self.threads.pop(num)
                        break
        if self.number_of_threads == 0:
            self.on_end_scanning()

    def on_end_scanning(self):
            self.isScanEnabled = False
            self.ui.startButton.setText("Start")
            self.storage.save()

    def stopScan(self):
        while self.threads:
            scan_worker, scan_thread = self.threads[0]
            if scan_worker.isRunning:
                scan_worker.stop()

    def log_text(self, string):
        self.ui.dataText.append("[" + str(datetime.datetime.now()) + "] " + str(string))


class ScanWorker(QObject):

    log_signal = pyqtSignal(str)
    exit_signal = pyqtSignal()

    def __init__(self, ip_generator, scanner, storage, **kwargs):
        super().__init__()
        self.ip_generator = ip_generator
        self.storage = storage
        self.scanner = scanner
        self.previous_address = None
        self.isRunning = True

    @pyqtSlot()
    def work(self):
        while self.isRunning:
            scan_address = self.ip_generator.get_next_address(self.previous_address)
            if not scan_address:
                break
            self.previous_address = scan_address
            scan_result = self.scanner.scan_address(scan_address)
            self.storage.put_responce(scan_address, scan_result)
            if scan_result == 0:
                self.log_signal.emit('%s has open port: %s' % scan_address)
            else:
                self.log_signal.emit('%s has closed port: %s' % scan_address)
        self.stop()

    def stop(self):
        self.isRunning = False
        self.exit_signal.emit()
