from qfluentwidgets import RadioButton, LineEdit, BodyLabel

# from Compoment.DubbingParamWindows2 import language_code
from Config import ROLE_ANNO_FOLDER
import sys
import os
import re
import datetime
import traceback
from concurrent.futures import ThreadPoolExecutor

from PyQt5.QtCore import Qt, QPropertyAnimation, QPoint, QTimer, QThread, pyqtSignal
from PyQt5.QtGui import QFont
from PyQt5.QtWidgets import QWidget, QFileDialog, QFrame, QVBoxLayout, \
    QInputDialog, QMessageBox, QMenu, QApplication, QSizePolicy, QDialog, QFormLayout, QLabel, QButtonGroup, \
    QHBoxLayout, QLineEdit

from Compoment.DraggableTextEdit import DraggableTextEdit
from Compoment.FileUploadArea import FileUploadArea
from Compoment.PathDialog import PrettyPathDialog
from Service.generalUtils import time_str_to_ms, ms_to_time_str
from Service.videoUtils import _probe_video_duration_ms
# from ThreadWorker.AnnotationAudioFeatureWorker import BatchAnnotationWorker_with_AudioFeature
from ThreadWorker.AnnotationExperiment import BatchAnnotationWorker_with_AudioFeature, \
    BatchAnnotationWorker_with_AudioFeature_no_split
from UI.Ui_annotation import Ui_Annotation
# from Service.dubbingMain.llmAPI import LLMAPI
from Service.subtitleUtils import parse_subtitle



class AnnotationInterface(Ui_Annotation, QFrame):


    def __init__(self, parent=None):
        super().__init__()
        print("批量标注界面加载")
        self.setupUi(self)
        self.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.worker = None
        self.loading_msg = None
        # 初始化字幕滚动列表和角色列表
        self._setup_unfinished_ui()

    def _setup_unfinished_ui(self):

        self.annotation_options_radio_widget = QWidget()
        # self.annotation_options_radio_widget.setLayout(QVBoxLayout)
        layout = QHBoxLayout(self.annotation_options_radio_widget)
        layout.setContentsMargins(0,0,0,0)
        self.operate_container.layout().insertWidget(0, self.annotation_options_radio_widget)

        self.options = ["旧版标注（较快）", "新版标注（较慢）", "新版标注（自动合并为长视频）"]
        self.button1 = RadioButton(self.options[0])
        self.button2 = RadioButton(self.options[1])
        self.button3 = RadioButton(self.options[2])
        layout.addWidget(self.button1)
        layout.addWidget(self.button2)
        layout.addWidget(self.button3)
        # layout.addWidget(self.button3)

        # 将单选按钮添加到互斥的按钮组
        self.buttonGroup = QButtonGroup(self.annotation_options_radio_widget)
        self.buttonGroup.addButton(self.button1)
        self.buttonGroup.addButton(self.button2)
        self.buttonGroup.addButton(self.button3)
        self.button3.setChecked(True)
        self.extraOutputBtn.hide()

        self.annotation_language_widget = QWidget()
        layout1 = QHBoxLayout(self.annotation_language_widget)
        layout1.setContentsMargins(0, 0, 0, 0)
        layout1.setSpacing(10)
        self.language_input = LineEdit()
        self.language_input.setText("中文")
        self.sub_language_input = LineEdit()
        self.sub_language_input.setText("中文")
        layout1.addWidget(BodyLabel("视频语言:"))
        layout1.addWidget(self.language_input)
        layout1.addWidget(BodyLabel("字幕语言:"))
        layout1.addWidget(self.sub_language_input)
        self.operate_container.layout().insertWidget(0, self.annotation_language_widget)



        self.font = QFont()
        self.font.setFamily("微软雅黑")
        self.font.setPointSize(15)
        self.font.setBold(True)
        self.font.setWeight(75)
        self.scrollArea.setHorizontalScrollBarPolicy(Qt.ScrollBarAlwaysOff)
        self.extractBtn.setFixedHeight(40)
        self.scrollArea.setStyleSheet(
            """ #scrollArea{ border: None; background: transparent; } #scrollAreaWidgetContents_2{ background: transparent; } """)

        self.videoBox.setLayout(QVBoxLayout())
        self.videoBox.layout().setContentsMargins(0,0,0,0)
        self.compress_video_upload_area = FileUploadArea(label_text="视频文件", file_types=["*.mp4", "*.avi"])
        self.videoBox.layout().addWidget(self.compress_video_upload_area)

        self.subtitleBox.setLayout(QVBoxLayout())
        self.subtitleBox.layout().setContentsMargins(0,0,0,0)
        self.merge_subtitle_upload_area = FileUploadArea(label_text="字幕文件", file_types=["*.srt", "*.txt"])
        self.subtitleBox.layout().addWidget(self.merge_subtitle_upload_area)

        self.role_info_edit = DraggableTextEdit()
        self.role_info_edit.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.role_info_edit.setPlaceholderText(
            "请在这里填写主角信息，包含角色名（必填）、角色特征、人物关系、参与的情节等")
        self.role_info_edit.setFont(QFont("Microsoft YaHei", 12))
        self.role_info_edit.setStyleSheet("""
                    QTextEdit {
                        border: 1px solid #ddd;
                        border-radius: 6px;
                        padding: 8px;
                    }
                """)
        layout = QVBoxLayout()
        layout.setContentsMargins(2,0,9,0)
        label = QLabel("主角信息")
        label.setFont(self.font)
        layout.addWidget(label)
        layout.addWidget(self.role_info_edit)
        layout.setStretch(1, 4)
        self.info_container.setLayout(layout)
        self.info_container.setMinimumHeight(180)

        # wire button
        self.extractBtn.clicked.connect(self._on_extract_clicked)
        self.operate_container.setMinimumHeight(120)


    def _on_general_finished(self, result: dict):
        if isinstance(self.loading_msg, QMessageBox):
            self.loading_msg.hide()
        if self.worker:
            self.worker.deleteLater()
            self.worker = None
        # QMessageBox.information(self, "提示", result["msg"])
        dlg = PrettyPathDialog("任务完成!", result["msg"], result["result_path"], parent=self)
        dlg.exec_()

    def _on_extract_clicked(self):

        print(self.buttonGroup.checkedButton().text())
        self.annotation_option = self.options.index(self.buttonGroup.checkedButton().text())
        print(self.annotation_option)
        # if self.buttonGroup.checkedButton().text() == self.options[0]:
        #     self.annotation_option =1
        # else:
        #     self.annotation_option =2
        """Validate inputs and start batch role annotation worker."""
        video_paths = self.compress_video_upload_area.file_paths if hasattr(self, 'compress_video_upload_area') else []
        subtitle_paths = self.merge_subtitle_upload_area.file_paths if hasattr(self, 'merge_subtitle_upload_area') else []
        role_info = self.role_info_edit.toPlainText().strip() if hasattr(self, 'role_info_edit') else ""

        if not video_paths or not subtitle_paths:
            QMessageBox.warning(self, "警告", "请同时上传视频文件和字幕文件")
            return

        if len(video_paths) != len(subtitle_paths):
            QMessageBox.warning(self, "警告", "视频与字幕数量不一致，请检查后重试")
            return

        pairs = list(zip(video_paths, subtitle_paths))

        print(video_paths)
        # print(pairs)

        # loading dialog
        self.loading_msg = QMessageBox(self)
        self.loading_msg.setWindowTitle("请稍候")
        self.loading_msg.setText("正在进行批量角色标注，请稍候...")
        self.loading_msg.setStandardButtons(QMessageBox.NoButton)
        self.loading_msg.setModal(True)
        self.loading_msg.show()
        QApplication.processEvents()

        # start worker
        timestamp = datetime.datetime.now().strftime("%Y%m%d-%H%M%S")
        output_root = os.path.join(ROLE_ANNO_FOLDER, f"批量角色标注-{os.path.splitext(os.path.basename(video_paths[0]))[0]}{timestamp}")

        if self.annotation_option == 0:
            self.worker = BatchAnnotationWorker(pairs, role_info, output_root, self.extraOutputBtn.isChecked())
        elif self.annotation_option == 1:
            self.worker = BatchAnnotationWorker_with_AudioFeature(pairs, role_info, output_root, self.extraOutputBtn.isChecked(), if_translate=self.language_input.text() != self.sub_language_input.text(), language= self.language_input.text())
        elif self.annotation_option == 2:
            self.worker = BatchAnnotationWorker_with_AudioFeature_no_split(pairs, role_info, output_root, self.extraOutputBtn.isChecked(), if_translate=self.language_input.text() != self.sub_language_input.text(), language=self.language_input.text())

        # self.worker = BatchAnnotationWorker_with_AudioFeature(pairs, role_info, output_root, self.extraOutputBtn.isChecked(), if_translate=self.annotation_option == 2)
        self.worker.progress.connect(self._on_progress)
        self.worker.finished.connect(self._on_general_finished)
        self.worker.start()

    def _on_progress(self, value: int, text: str):
        if isinstance(self.loading_msg, QMessageBox):
            if value >= 0:
                if text:
                    self.loading_msg.setText(text)
            QApplication.processEvents()

class BatchAnnotationWorker(QThread):
    """
    QThread worker that uses a ThreadPoolExecutor to annotate roles for each (video, srt) pair in parallel.
    """
    finished = pyqtSignal(dict)
    progress = pyqtSignal(int, str)

    def __init__(self, pairs, role_info_text, output_root_dir, extraOutput=False, max_workers=4):
        super().__init__()
        self.pairs = pairs
        self.role_info_text = role_info_text
        self.output_root_dir = output_root_dir
        self.max_workers = max_workers
        self.extraOutput = extraOutput

    def run(self):
        try:
            os.makedirs(self.output_root_dir, exist_ok=True)
            self.summary_dir = os.path.join(self.output_root_dir, "剧情简介")
            self.srt_dir = os.path.join(self.output_root_dir, "字幕")
            self.role_dir = os.path.join(self.output_root_dir, "角色表")
            os.makedirs(self.summary_dir, exist_ok=True)
            os.makedirs(self.srt_dir, exist_ok=True)
            os.makedirs(self.role_dir, exist_ok=True)
            from Service.dubbingMain.llmAPI import LLMAPI

            LLMAPI.getInstance()  # initialize once

            def process_one(idx, video_path, srt_path):
                # 1) optional plot summary to help LLM; not strictly required by spec, but improves accuracy
                try:
                    plot_summary = LLMAPI.getInstance().video_summary_batch("", video_path, self.role_info_text)
                except Exception:
                    plot_summary = ""

                # 2) read srt
                with open(srt_path, 'r', encoding='utf-8') as f:
                    subtitle_text = f.read()
                    subtitle_text = re.sub(r'\n{2,}', '\n\n', subtitle_text.strip())

                # 3) call LLM to extract roles with provided role info hint
                result_dict = LLMAPI.getInstance().extract_role_info_by_hint(subtitle_text, plot_summary, self.role_info_text)

                subtitle_list = parse_subtitle(srt_path)
                if not result_dict or len(subtitle_list) != len(result_dict):
                    raise Exception("字幕和角色标注结果数量不一致")

                result_roles_list = list(result_dict.values())

                # 4) write output srt and summary
                base_name = os.path.splitext(os.path.basename(srt_path))[0]
                # target_dir = os.path.join(self.output_root_dir, base_name)
                # os.makedirs(target_dir, exist_ok=True)
                summary_path = os.path.join(self.summary_dir, f"剧情简介{idx}.txt")
                output_srt_path = os.path.join(self.srt_dir, f"{base_name}_{idx}_角色标注.srt")
                role_table_file = os.path.join(self.role_dir, f"角色表{idx}.txt")

                if plot_summary:
                    with open(summary_path, 'w', encoding='utf-8') as f:
                        f.write(plot_summary)

                with open(output_srt_path, 'w', encoding='utf-8') as f:
                    for i, sub in enumerate(subtitle_list):
                        f.write(f"{sub['index']}\n")
                        f.write(f"{sub['start']} --> {sub['end']}\n")
                        f.write(f"{result_roles_list[i]}: {sub['text']}\n\n")
                with open(role_table_file, "w", encoding="utf-8") as f:
                    f.write(";".join(result_roles_list))
                duration_ms = _probe_video_duration_ms(video_path)
                return output_srt_path, duration_ms


            total = len(self.pairs)
            completed = 0
            failed = []
            self.progress.emit(0, f"开始处理，共 {total} 组...   ")

            from concurrent.futures import as_completed
            import ffmpeg

            # 存储成功条目的 (导出字幕路径, 视频时长ms)，按原顺序
            sub_results = [None] * total
            with ThreadPoolExecutor(max_workers=self.max_workers) as executor:
                future_to_ctx = {}
                for i, (v, s) in enumerate(self.pairs):
                    fut = executor.submit(process_one, i, v, s)
                    future_to_ctx[fut] = (i, v, s)
                for fut in as_completed(future_to_ctx):
                    i, v, s = future_to_ctx[fut]
                    try:
                        out_srt, dur_ms = fut.result()
                        sub_results[i] = (out_srt, dur_ms)
                    except Exception as e:
                        failed.append((os.path.basename(v), os.path.basename(s), str(e), traceback.format_exc()))
                    finally:
                        completed += 1
                        pct = int(completed / total * 100)
                        self.progress.emit(pct, f"正在处理：{completed}/{total}，失败 {len(failed)}...   ")

            failed2 = []
            # save error log if any
            if failed:
                error_log_path = os.path.join(self.output_root_dir, "error_log.txt")
                with open(error_log_path, 'w', encoding='utf-8') as f:
                    f.write("发生错误的条目如下:\n\n")
                    for vname, sname, err, tb in failed:
                        f.write(f"视频: {vname}  字幕: {sname}\n错误: {err}\n{tb}\n---\n")
            elif self.extraOutput:
                # 先合并字幕：使用成功项，按原顺序叠加 offset（累计时长）
                try:
                    self.progress.emit(1, "  合并字幕中...  ")
                    merged_subtitle_path = os.path.join(self.output_root_dir, "merged_subtitle.srt")
                    current_index = 1
                    merged_lines = []
                    cumulative_offset = 0
                    for res in sub_results:
                        if res is None:
                            continue
                        path, duration_ms = res
                        with open(path, "r", encoding="utf-8") as f:
                            content = f.read()
                        blocks = re.split(r"\n\s*\n", content.strip(), flags=re.MULTILINE)
                        i_block = 1
                        for block in blocks:
                            lines = block.strip().split("\n")
                            if len(lines) < 2:
                                raise Exception(f"字幕文件{path}第{i_block}块格式错误")
                            time_line = lines[1] if "-->" in lines[1] else lines[0]
                            m = re.match(r"(\d{2}:\d{2}:\d{2},\d{3})\s*-->\s*(\d{2}:\d{2}:\d{2},\d{3})", time_line)
                            if not m:
                                raise Exception(f"字幕文件{path}第{i_block}块格式错误")
                            start_time, end_time = m.groups()
                            start_ms = int(time_str_to_ms(start_time) + cumulative_offset)
                            end_ms = int(time_str_to_ms(end_time) + cumulative_offset)
                            new_block = [str(current_index)]
                            new_block.append(f"{ms_to_time_str(start_ms)} --> {ms_to_time_str(end_ms)}")
                            if "-->" in lines[1]:
                                new_block.extend(lines[2:])
                            else:
                                raise Exception(f"字幕文件{path}第{i_block}块格式错误")
                            merged_lines.append("\n".join(new_block))
                            current_index += 1
                            i_block += 1
                        cumulative_offset += max(0, duration_ms)

                    with open(merged_subtitle_path, "w", encoding="utf-8") as f:
                        f.write("\n\n".join(merged_lines))
                except Exception:
                    failed2.append(("MERGE", "SUBTITLE", "合并字幕失败", traceback.format_exc()))

                try:
                    merged_video_path = os.path.join(self.output_root_dir, "merged_video.mp4")
                    video_files_ok = [v for (res, (v, s)) in zip(sub_results, self.pairs) if res is not None]
                    self.progress.emit(2, "  合并视频中...  ")
                    streams = []
                    for fpath in video_files_ok:
                        inp = ffmpeg.input(fpath)
                        v = inp.video
                        a = inp.audio.filter('aresample', **{'async': 1, 'first_pts': 0})
                        streams += [v, a]
                    concat = ffmpeg.concat(*streams, v=1, a=1, n=len(video_files_ok)).node
                    vcat, acat = concat[0], concat[1]
                    (
                        ffmpeg
                        .output(vcat, acat, merged_video_path, vcodec='libx264', acodec='aac')
                        .global_args('-fflags', '+genpts')
                        .overwrite_output()
                        .run()
                    )
                except Exception:
                    failed2.append(("MERGE", "VIDEO", "合并视频失败", traceback.format_exc()))


            msg = f"批量角色标注完成，成功 {total - len(failed)}，失败 {len(failed)}。"
            if failed2:
                msg2 = {info[2] for info in failed2}
                msg += str(msg2)
            self.finished.emit({
                "msg": msg,
                "result_path": self.output_root_dir
            })
        except Exception as e:
            self.finished.emit({
                "msg": f"发生错误: {e}",
                "result_path": self.output_root_dir if os.path.isdir(self.output_root_dir) else ""
            })






if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = AnnotationInterface()
    # 测试视频
    # window.compress_video_upload_area.add_files([r"E:\offer\配音任务2\伤心者联盟\merged_video_20250915150343.mp4"])
    # window.merge_subtitle_upload_area.add_files([r"E:\offer\配音任务2\伤心者联盟\merged_subtitle_20250915150314.srt"])

    # 第一集视频
    # window.compress_video_upload_area.add_files([r"E:\offer\配音任务2\伤心者联盟\1_2.mp4"])
    # window.merge_subtitle_upload_area.add_files([r"E:\offer\配音任务2\伤心者联盟\1_2.srt"])

    # 第1~8集视频，20分钟，477条字幕
    window.compress_video_upload_area.add_files([r"E:\offer\配音任务2\伤心者联盟\测试长视频1_8\1_8.mp4"])
    window.merge_subtitle_upload_area.add_files([r"E:\offer\配音任务2\伤心者联盟\测试长视频1_8\中文.srt"])


#     window.role_info_edit.setText("""苏清雪：路辰的妻子，与江浩辰互相出轨
# 路辰：苏清雪的丈夫
# 江浩辰：童颜的丈夫，与苏清雪在外低俗娱乐
# 童颜：江浩辰妻子
# 吴佳佳：苏清雪闺蜜，煽风点火，推动剧情发展""")
    window.show()
    sys.exit(app.exec_())

