import datetime
import os

import ffmpeg


def _probe_video(path):
    """获取视频的元信息"""
    try:
        info = ffmpeg.probe(path)
        video_stream = next((s for s in info['streams'] if s['codec_type'] == 'video'), None)
        audio_stream = next((s for s in info['streams'] if s['codec_type'] == 'audio'), None)
        if not video_stream:
            raise ValueError("No video stream found")
        return {
            'width': int(video_stream.get('width', 0)),
            'height': int(video_stream.get('height', 0)),
            'fps': eval(video_stream.get('r_frame_rate', '0/1')),
            'v_codec': video_stream.get('codec_name', ''),
            'a_codec': audio_stream.get('codec_name', '') if audio_stream else '',
            'sample_rate': int(audio_stream.get('sample_rate', 0)) if audio_stream else 0,
        }
    except Exception as e:
        raise ValueError(f"Failed to probe {path}: {e}")


def _can_copy_merge(base_info, other_info):
    """判断是否可以无损合并（所有视频格式一致）"""
    return (
            base_info['v_codec'] == other_info['v_codec'] and
            base_info['a_codec'] == other_info['a_codec'] and
            base_info['width'] == other_info['width'] and
            base_info['height'] == other_info['height'] and
            abs(base_info['fps'] - other_info['fps']) < 0.01 and
            base_info['sample_rate'] == other_info['sample_rate']
    )


def merge_video(video_files: list[str], id: int = 0, result_dir: str="", output_filename: str="") -> dict:
    if not video_files:
        return {"msg": "视频文件列表为空", "result_path": ""}

    if not result_dir:
        filedir = os.path.dirname(video_files[0])
        result_dir = os.path.join(filedir, "merged")
        os.makedirs(result_dir, exist_ok=True)
    if not output_filename:
        output_filename = f"merged_video_{os.path.basename(video_files[0])}.mp4"
    # output_filename = f"merged_video_{os.path.basename(video_files[0])}.mp4"
    output_path = os.path.join(result_dir, output_filename)

    try:
        # 1. 探测第一个视频作为基准
        base_info = _probe_video(video_files[0])
        print(f"基准视频格式: {base_info}")

        # 2. 检查是否所有视频都兼容 copy 合并
        use_copy = True
        for f in video_files[1:]:
            info = _probe_video(f)
            if not _can_copy_merge(base_info, info):
                use_copy = False
                break

        if use_copy:
            print("✅ 所有视频格式一致，使用无损快速合并（-c copy）")
            # 构建 concat 输入列表文件（避免命令行过长）
            list_file = os.path.join(result_dir, f"input_files_{id}.txt")
            with open(list_file, 'w', encoding='utf-8') as f:
                for vf in video_files:
                    f.write(f"file '{vf}'\n")

            (
                ffmpeg
                .input(list_file, format='concat', safe=0)
                .output(output_path, c='copy')
                .overwrite_output()
                .run()
            )
            os.remove(list_file)  # 清理临时文件
        else:
            print("⚠️ 视频格式不一致，启用重编码合并（统一到基准格式）")
            streams = []
            has_audio = False

            for idx, f in enumerate(video_files):
                inp = ffmpeg.input(f)
                v = inp.video
                a = inp.audio if any(s['codec_type'] == 'audio' for s in ffmpeg.probe(f)['streams']) else None

                # 统一视频：缩放+帧率对齐（以第一个视频为准）
                if idx > 0:
                    v = v.filter('scale', base_info['width'], base_info['height'])
                    # 可选：强制帧率（如果差异大）
                    # v = v.filter('fps', base_info['fps'])

                # 统一音频：重采样 + aresample 对齐
                if a is not None:
                    a = a.filter('aresample', **{
                        'async': 1,
                        'first_pts': 0,
                        'sample_rate': base_info['sample_rate'] or 44100
                    })
                else:
                    a = ffmpeg.input('anullsrc', sample_rate=base_info['sample_rate'] or 44100,
                                     duration=ffmpeg.probe(f)['format']['duration']).audio

                streams += [v, a]

            concat = ffmpeg.concat(*streams, v=1, a=1, n=len(video_files)).node
            vcat = concat[0]
            acat = concat[1]

            out = ffmpeg.output(
                vcat, acat, output_path,
                vcodec='libx264',
                acodec='aac',
                preset="fast",
                crf=28
            ).global_args('-fflags', '+genpts').overwrite_output()

            out.run()

        print(f"✅ 视频合并完成: {output_path}")
        return {
            "msg": f"视频合并完成！保存路径如下：{output_path}",
            "result_path": output_path
        }

    except Exception as e:
        print(f"❌ 视频合并出错: {e}")
        return {
            "msg": f"视频合并失败: {str(e)}",
            "result_path": ""
        }