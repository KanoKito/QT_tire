import sys
import time
import glob
import chardet
import html
from PyQt5.QtWidgets import (QApplication, QWidget, QVBoxLayout, QHBoxLayout,
                             QPushButton, QFileDialog, QLineEdit, QTextEdit,
                             QLabel, QMessageBox, QTabWidget)
from PyQt5.QtCore import QThread, QObject, pyqtSignal


def detect_encoding(file_path):
    """Определение кодировки файла"""
    with open(file_path, 'rb') as f:
        rawdata = f.read(10000)
        if not rawdata:
            return 'utf-8'
        result = chardet.detect(rawdata)
        return result['encoding'] if result['confidence'] > 0.5 else 'windows-1251'


def read_data(path, encoding):
    """Чтение файлов в бинарном режиме с ручным декодированием"""
    for filename in glob.glob(path):
        try:
            with open(filename, 'rb') as f:
                content = f.read().decode(encoding, errors='replace')
                for line in content.splitlines():
                    yield line.strip()
        except Exception as e:
            print(f"Ошибка чтения файла {filename}: {str(e)}")
            continue


class Worker(QObject):
    finished = pyqtSignal()
    progress = pyqtSignal(str)
    result = pyqtSignal(int, int, float, str)
    data_ready = pyqtSignal(list, list, str)

    def __init__(self, file_path):
        super().__init__()
        self.file_path = file_path
        self.encoding = 'utf-8'
        self.tires = []
        self.kiz = []

    def run(self):
        start_time = time.time()
        tire_names = set()

        try:
            files = glob.glob(self.file_path)
            if not files:
                raise ValueError("Файлы для обработки не найдены")

            self.encoding = detect_encoding(files[0])
            self.progress.emit(f"Определена кодировка: {self.encoding}")

            for line in read_data(self.file_path, self.encoding):
                if "НаимДокОтгр=" in line:
                    d_start = line.find('НаимДокОтгр=') + len('НаимДокОтгр=')
                    d_end = line.find('НомДокОтгр=')
                    d1_start = line.find('НомДокОтгр=') + len('НомДокОтгр=')
                    d1_end = line.find('ДатаДокОтгр=')
                    d2_start = line.find('ДатаДокОтгр=') + len('ДатаДокОтгр=')
                    d2_end = line.find('/>')

                    if d2_end != -1:
                        tire_data = f"{line[d_start:d_end]}:{line[d1_start:d1_end]}:{line[d2_start:d2_end]}"
                        self.tires.append(tire_data)
                        tire_names.add(tire_data)

                if "НаимТов" in line:
                    start = line.find('НаимТов=') + len('НаимТов=')
                    end = line.find('ОКЕИ_Тов=')

                    if end != -1:
                        tire_name = html.unescape(line[start:end])
                        self.tires.append(tire_name)
                        tire_names.add(tire_name)

                if "<КИЗ>" in line:
                    start = line.find("<КИЗ>") + len("<КИЗ>")
                    end = line.find("</КИЗ>")

                    if end != -1:
                        kiz_code = html.unescape(line[start:end])
                        self.tires.append(kiz_code)
                        self.kiz.append(kiz_code)

            self.progress.emit(f"Обработано файлов: {len(files)}")
            self.data_ready.emit(self.tires, self.kiz, self.encoding)

        except Exception as e:
            self.progress.emit(f"Ошибка: {str(e)}")
        finally:
            elapsed = time.time() - start_time
            self.result.emit(
                len(tire_names), len(self.kiz), elapsed, self.encoding)
            self.finished.emit()


class MainWindow(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()
        self.selected_file = ""
        self.worker_thread = None

    def initUI(self):
        self.setWindowTitle('XML Processor')
        self.setGeometry(200, 200, 800, 600)

        main_layout = QVBoxLayout()

        # Панель управления
        control_layout = QHBoxLayout()
        self.btn_choose = QPushButton('Выбрать файл', self)
        self.btn_choose.clicked.connect(self.chooseFile)
        self.file_edit = QLineEdit(self)
        self.file_edit.setReadOnly(True)
        control_layout.addWidget(self.btn_choose)
        control_layout.addWidget(self.file_edit)
        main_layout.addLayout(control_layout)

        # Кнопка запуска
        self.btn_start = QPushButton('Начать обработку', self)
        self.btn_start.clicked.connect(self.startProcessing)
        main_layout.addWidget(self.btn_start)

        # Вкладки с результатами
        self.tabs = QTabWidget()

        # Вкладка с шинами
        self.tire_tab = QWidget()
        tire_layout = QVBoxLayout()
        self.tire_list = QTextEdit()
        self.tire_list.setReadOnly(True)
        tire_layout.addWidget(QLabel("Найденные данные (первые 500 записей):"))
        tire_layout.addWidget(self.tire_list)
        self.tire_tab.setLayout(tire_layout)

        # Вкладка с КИЗ
        self.kiz_tab = QWidget()
        kiz_layout = QVBoxLayout()
        self.kiz_list = QTextEdit()
        self.kiz_list.setReadOnly(True)
        kiz_layout.addWidget(QLabel(
            "Коды идентификации (первые 500 записей):"))
        kiz_layout.addWidget(self.kiz_list)
        self.kiz_tab.setLayout(kiz_layout)

        self.tabs.addTab(self.tire_tab, "Данные о шинах")
        self.tabs.addTab(self.kiz_tab, "КИЗ коды")
        main_layout.addWidget(self.tabs)

        # Статусная строка
        self.status = QLabel('Готово к работе')
        main_layout.addWidget(self.status)

        self.setLayout(main_layout)

    def chooseFile(self):
        file_name, _ = QFileDialog.getOpenFileName(
            self, 'Выберите XML файл', '', 'XML files (*.xml)')
        if file_name:
            self.selected_file = file_name
            self.file_edit.setText(file_name)

    def startProcessing(self):
        if not self.selected_file:
            QMessageBox.warning(self, 'Ошибка', 'Выберите файл для обработки!')
            return

        self.btn_choose.setEnabled(False)
        self.btn_start.setEnabled(False)
        self.tire_list.clear()
        self.kiz_list.clear()

        self.worker_thread = QThread()
        self.worker = Worker(self.selected_file)
        self.worker.moveToThread(self.worker_thread)

        self.worker_thread.started.connect(self.worker.run)
        self.worker.progress.connect(self.status.setText)
        self.worker.data_ready.connect(self.show_data)
        self.worker.result.connect(self.handleResult)
        self.worker.finished.connect(self.worker_thread.quit)
        self.worker.finished.connect(self.worker.deleteLater)
        self.worker_thread.finished.connect(self.worker_thread.deleteLater)
        self.worker_thread.finished.connect(
            lambda: (self.btn_choose.setEnabled(True),
                     self.btn_start.setEnabled(True)))

        self.worker_thread.start()

    def show_data(self, tires, kiz):
        """Отображение данных в интерфейсе"""
        self.tire_list.setPlainText('\n'.join(tires[:500]))
        self.kiz_list.setPlainText('\n'.join(kiz[:500]))

    def handleResult(self, unique, total, time, encoding):
        self.status.setText(
            f"Обработка завершена за {time:.2f} сек | "
            f"Кодировка: {encoding} | "
            f"Уникальные: {unique} | Всего КИЗ: {total}"
        )


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = MainWindow()
    window.show()
    sys.exit(app.exec_())
