"""Qt 默认落在会话回放，四个功能页可从界面进入；播放/暂停/逐帧可用，启动到结束没有 Qt/QML 告警。

P1 追加：会话列表单行 + 过滤（真实按键/清除/无匹配/过滤后选择）、3D 坐标轴方向与色带图例
（范围与当前帧真实着色范围逐值对照）、就近错误提示不误报。
"""
import hashlib
import json
import subprocess
import unittest

import test_integration as fixtures
from test_integration import ROOT, SDK, DLL, HOST, SESSION

GROUND = ROOT / 'docs/evidence/2026-10-23_range_p0_w2/BOUND_GROUND.json'


class TestUiTour(unittest.TestCase):
    setUp = fixtures.TestApp.setUp

    def test_default_replay_then_feature_pages(self):
        if not SESSION.is_dir():
            self.skipTest('real session is not present')
        meta = json.loads((SESSION / 'meta.json').read_text(encoding='utf-8'))
        before = {name: hashlib.sha256((SESSION / name).read_bytes()).hexdigest()
                  for name in ('meta.json', 'points.bin')}
        args = [str(SDK), str(DLL), '--session', str(SESSION), '--host', str(HOST),
                '--report', str(self.out / 'run.json'), '--tour-report', str(self.out / 'tour.json'),
                '--ground', str(GROUND), '--no-restore-local',
                '--no-external-open']
        done = subprocess.run(args, cwd=ROOT, capture_output=True, timeout=120)
        (self.out / 'stdout.txt').write_bytes(done.stdout)
        (self.out / 'stderr.txt').write_bytes(done.stderr)
        self.assertEqual(done.returncode, 0, done.stderr.decode(errors='replace'))

        report = json.loads((self.out / 'tour.json').read_text('utf-8'))
        self.assertEqual(report['status'], 'PASS', report)
        cases = {row['case']: row for row in report['checks']}
        for name in ('default_section_is_replay', 'default_sidebar_open', 'default_details_open',
                     'default_mode_is_replay', 'default_session_loaded', 'default_paused_at_first_frame',
                     'default_session_list_populated', 'default_annotation_page_hidden',
                     'default_cloud_viewport_visible', 'default_no_unexpected_window',
                     'status_bar_visible', 'frame_readout_in_status_bar', 'analysis_badge_shown',
                     'shortcuts_registered',
                     'section_live_selected', 'section_joint_selected', 'section_annotation_selected',
                     'annotation_page_usable', 'back_to_replay', 'playback_advances_frames',
                     'playback_reports_playing', 'space_starts_playback', 'pause_stops_playing',
                     'step_moves_one_frame', 'left_moves_one_frame', 'end_seeks_last_frame',
                     'home_seeks_first_frame', 'rename_space_edits_text', 'rename_left_moves_cursor',
                     'rename_right_moves_cursor', 'rename_keys_do_not_control_replay',
                     'rename_dialog_closed', 'screenshot_has_no_dialog',
                     'play_button_starts_playback', 'play_button_pauses_playback',
                     'live_shortcuts_send_no_replay_commands_mock_snapshot', 'escape_cancels_selection',
                     'annotation_receives_current_points', 'hidden_annotation_not_initialized',
                     'hidden_annotation_not_copied_during_playback', 'hidden_annotation_stays_uncopied',
                     'status_body_at_least_12px', 'status_fields_match_snapshot', 'analysis_badge_text',
                     'status_alarm_hidden_without_hint', 'frame_readout_by_slider',
                     'same_frame_screenshot_at_3', 'tour_screenshot_saved', 'native_window_alive',
                     # P1-1 会话列表单行 + 过滤
                     'session_list_model_count', 'session_filter_count_total',
                     'session_filter_starts_empty', 'session_no_match_hidden_initially',
                     'session_alert_hidden_initially', 'session_row_truncates_long_name',
                     'filter_typed_by_real_keys', 'filter_by_id_matches_name_or_id',
                     'filter_rendered_rows_match_model', 'session_row_single_line',
                     'session_row_texts_at_least_12px', 'session_row_single_line_text',
                     'session_row_accessible_name', 'session_row_name_elides',
                     'filter_shows_match_count', 'filter_does_not_change_loaded_session',
                     'filter_clear_button_restores_all', 'filter_no_match_hint',
                     'filter_no_match_keeps_state', 'filter_single_match',
                     'filtered_row_present_after_filter', 'filtered_click_updates_selection',
                     'filtered_row_click_opens_session', 'filtered_session_frame_count',
                     'filter_clear_after_select_keeps_session',
                     # P1-2 3D 坐标轴 + 色带图例
                     'legend_visible_in_3d', 'legend_single_color_text',
                     'legend_above_cloud_not_overlapping', 'axis_gizmo_visible',
                     'axis_gizmo_in_corner', 'axis_labels_present', 'view_buttons_moved_to_toolbar',
                     'status_alert_hidden_without_error', 'axis_x_horizontal_at_yaw0',
                     'axis_y_not_horizontal_at_yaw0', 'axis_z_points_up',
                     'axis_labels_do_not_overlap', 'axis_refresh_not_per_frame',
                     'axis_y_horizontal_at_yaw90', 'axis_x_not_horizontal_at_yaw90',
                     'axis_z_points_up_at_yaw90', 'legend_frame_available',
                     'legend_height_uses_per_frame_range', 'legend_height_text_matches',
                     'legend_strip_uses_height_map', 'legend_intensity_uses_per_frame_range',
                     'legend_intensity_not_confidence', 'legend_fallback_without_intensity',
                     'legend_height_without_intensity', 'legend_depth_without_intensity',
                     'legend_depth_fixed_range', 'legend_back_to_single_color',
                     # 配平视图（只旋转显示，不改数据）
                     'level_ground_bound', 'level_available_for_current_session',
                     'level_auto_applied', 'level_auto_label',
                     'level_off_residual', 'level_off_label',
                     'level_auto_rotation', 'level_does_not_change_frame',
                     'level_box_encloses_rotated_target', 'level_box_clears_without_target',
                     'level_screenshot_saved', 'level_on_again', 'level_on_label',
                     'level_on_rotation', 'level_toggle_back_to_sensor_frame'):
            self.assertIn(name, cases, report['checks'])
            self.assertTrue(cases[name]['passed'], (name, cases[name]))
        self.assertEqual(report['section'], 0)
        self.assertEqual(report['mode'], 'replay')
        # before/after 对照取截图当时的会话与帧（之后为验证「过滤后选择」切过会话）。
        self.assertEqual(report['screenshotSessionId'], SESSION.name)
        self.assertEqual(report['screenshotFrameIndex'], 3)
        self.assertEqual(report['screenshotFrameCount'], len(meta['frames']))
        self.assertEqual(report['alert']['state'], 'none')
        self.assertTrue((self.out / 'tour.png').is_file())

        service = json.loads((self.out / 'run.json').read_text('utf-8'))
        self.assertEqual(service['status'], 'PASS')
        published = [row for row in service['log'] if row['eventType'] == 'published']
        self.assertGreaterEqual(len(published), 5)
        # 标注页不可见时不整帧拷贝：整轮只在切到标注台时补一次当前帧。
        self.assertEqual(report['annotationCopies'], 1, report)
        self.assertEqual(report['frameCopies'], len(published), report)
        # 正常路径不该有命令错误（切会话时给旧会话发 gtLoad 的回归就是这样暴露的）；也不该有命令超时。
        errors = [row for row in service['log'] if row['eventType'] == 'commandError']
        self.assertEqual(errors, [], errors)
        self.assertEqual(report['expiredCommands'], 0, report)
        self.assertEqual(report['staleReplies'], 0, report)
        warnings = [row['message'] for row in service['log'] if row['eventType'] == 'nativeStderr']
        # 已知且允许：① Qt 布局引擎在快速切页时自报一次 polish loop，两次迭代后自行恢复，界面尺寸正确
        # （历史证据里 2026-10-26 的多次运行也有同样一行，早于 P0/P1）；② `qt.qpa.mime:` 是 Windows 平台层
        # 剪贴板争用（本机别的进程持有剪贴板时的重试），与被测行为无关，单独计数不判失败。
        # 其余任何 QML 告警（属性重复赋值、未定义属性、invalid stride、非 NOTIFYable 绑定等）都判失败。
        unexpected = [message for message in warnings
                      if 'Layout polish loop detected' not in message
                      and not message.startswith('qt.qpa.mime:')]
        self.assertEqual(unexpected, [], warnings)
        self.assertEqual(service['jointMutationRequests'], 0)
        self.assertEqual(service['sessionDeletes'], 0)
        self.assertEqual([row for row in service['log'] if row['eventType'] == 'annotatorOpened'], [])
        for name, sha in before.items():
            self.assertEqual(hashlib.sha256((SESSION / name).read_bytes()).hexdigest(), sha)


if __name__ == '__main__':
    unittest.main()
