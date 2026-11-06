"""Append client UI translations without reformatting existing catalogs."""
import json
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parents[1]
LOCALES = ("zh_CN", "zh_TW", "ja_JP", "ko_KR", "es_ES")
TEXT = {
    "Client Settings": ["客户端设置", "用戶端設定", "クライアント設定", "클라이언트 설정", "Ajustes del cliente"],
    "Switch all keyboard and mouse input": ["一键切换全部键鼠输入", "一鍵切換全部鍵鼠輸入", "キーボード・マウス入力を一括切替", "모든 키보드 및 마우스 입력 전환", "Cambiar toda la entrada de teclado y ratón"],
    "System keyboard and mouse": ["系统键鼠输入", "系統鍵鼠輸入", "システムのキーボード・マウス入力", "시스템 키보드 및 마우스", "Teclado y ratón del sistema"],
    "Background window messages": ["后台窗口消息", "背景視窗訊息", "バックグラウンドのウィンドウメッセージ", "백그라운드 창 메시지", "Mensajes de ventana en segundo plano"],
    "Current input mode: {mode}": ["当前输入方式：{mode}", "目前輸入方式：{mode}", "現在の入力方式：{mode}", "현재 입력 방식: {mode}", "Modo de entrada actual: {mode}"],
    "System input uses the real keyboard and cursor. Keep the game focused. Changes apply between tasks.": ["系统输入会使用真实键盘和鼠标，请保持游戏位于前台。仅在任务空闲时切换。", "系統輸入會使用真實鍵盤與滑鼠，請保持遊戲位於前景。僅在任務閒置時切換。", "システム入力は実際のキーボードとカーソルを使います。ゲームを前面に保ってください。切替はタスク間で行います。", "시스템 입력은 실제 키보드와 커서를 사용합니다. 게임 포커스를 유지하세요. 작업 사이에 전환됩니다.", "La entrada del sistema usa el teclado y cursor reales. Mantén el juego enfocado. Los cambios se aplican entre tareas."],
    "Check independent channel": ["检查独立通道更新", "檢查獨立通道更新", "独立チャンネルの更新を確認", "독립 채널 업데이트 확인", "Comprobar el canal independiente"],
    "Download portable update": ["下载新版便携包", "下載新版可攜包", "ポータブル更新をダウンロード", "포터블 업데이트 다운로드", "Descargar actualización portable"],
    "Open update folder": ["打开更新目录", "開啟更新目錄", "更新フォルダーを開く", "업데이트 폴더 열기", "Abrir carpeta de actualizaciones"],
    "Import old configuration": ["导入旧配置", "匯入舊設定", "以前の設定をインポート", "이전 설정 가져오기", "Importar configuración anterior"],
    "Choose old configuration folder": ["选择旧配置目录", "選擇舊設定目錄", "以前の設定フォルダーを選択", "이전 설정 폴더 선택", "Elegir carpeta de configuración anterior"],
    "Import old configuration once. The current configuration is backed up and replaced on the next start.": ["可一次性导入旧配置。下次启动时会备份并替换当前配置。", "可一次性匯入舊設定。下次啟動時會備份並取代目前設定。", "以前の設定を一度だけ取り込めます。次回起動時に現在の設定をバックアップして置き換えます。", "이전 설정을 한 번 가져올 수 있습니다. 다음 시작 시 현재 설정을 백업하고 교체합니다.", "Importa la configuración anterior una vez. La actual se guardará y sustituirá al reiniciar."],
    "The current configuration will be backed up and replaced after restart. Continue?": ["重启后将备份并替换当前配置，是否继续？", "重新啟動後將備份並取代目前設定，是否繼續？", "再起動後に現在の設定をバックアップして置き換えます。続行しますか？", "다시 시작하면 현재 설정을 백업하고 교체합니다. 계속할까요?", "La configuración actual se guardará y sustituirá al reiniciar. ¿Continuar?"],
    "Staged {count} files. Restart to finish importing.": ["已暂存 {count} 个文件，重启后完成导入。", "已暫存 {count} 個檔案，重新啟動後完成匯入。", "{count} 個のファイルを準備しました。再起動して完了してください。", "파일 {count}개를 준비했습니다. 다시 시작해 완료하세요.", "Se prepararon {count} archivos. Reinicia para completar la importación."],
    "Stop the current task before importing configuration.": ["请先停止当前任务，再导入配置。", "請先停止目前任務，再匯入設定。", "設定を取り込む前に現在のタスクを停止してください。", "설정을 가져오기 전에 현재 작업을 중지하세요.", "Detén la tarea actual antes de importar la configuración."],
    "Stop the current task before switching input mode.": ["请先停止当前任务，再切换输入方式。", "請先停止目前任務，再切換輸入方式。", "入力方式を切り替える前に現在のタスクを停止してください。", "입력 방식을 바꾸기 전에 현재 작업을 중지하세요.", "Detén la tarea actual antes de cambiar el modo de entrada."],
    "No newer independent release available.": ["暂无更新的独立版本。", "暫無更新的獨立版本。", "新しい独立リリースはありません。", "새 독립 릴리스가 없습니다.", "No hay una versión independiente más reciente."],
    "Available version: {version}": ["可用版本：{version}", "可用版本：{version}", "利用可能なバージョン：{version}", "사용 가능한 버전: {version}", "Versión disponible: {version}"],
    "Update check failed: {error}": ["更新检查失败：{error}", "更新檢查失敗：{error}", "更新確認に失敗：{error}", "업데이트 확인 실패: {error}", "Error al comprobar actualizaciones: {error}"],
    "Update saved to {path}. Close the app and extract it over this portable folder; keep the data folder.": ["更新已保存至 {path}。请关闭程序后解压覆盖便携目录，并保留 data 目录。", "更新已儲存至 {path}。請關閉程式後解壓縮覆蓋可攜目錄，並保留 data 目錄。", "更新を {path} に保存しました。終了後に展開して置き換え、data フォルダーは保持してください。", "업데이트를 {path}에 저장했습니다. 앱을 닫고 압축을 덮어 푸세요. data 폴더는 유지하세요.", "Actualización guardada en {path}. Cierra la app y extrae sobre la carpeta portable; conserva data."],
    "Loading workshop cache...": ["正在读取工坊缓存…", "正在讀取工坊快取…", "工房キャッシュを読み込み中…", "워크숍 캐시 읽는 중…", "Cargando caché del taller…"],
    "Refresh workshop cache": ["刷新工坊缓存", "重新整理工坊快取", "工房キャッシュを更新", "워크숍 캐시 새로 고침", "Actualizar caché del taller"],
    "Refreshing workshop index and code cache...": ["正在更新工坊索引和全部代码缓存…", "正在更新工坊索引與全部程式碼快取…", "工房の索引とコードキャッシュを更新中…", "워크숍 목록 및 코드 캐시 갱신 중…", "Actualizando índice y caché de códigos del taller…"],
    "Offline cache from {time}": ["离线缓存，更新时间：{time}", "離線快取，更新時間：{time}", "オフラインキャッシュ：{time}", "오프라인 캐시: {time}", "Caché sin conexión de {time}"],
    "Workshop updated at {time}": ["工坊更新时间：{time}", "工坊更新時間：{time}", "工房更新日時：{time}", "워크숍 갱신 시간: {time}", "Taller actualizado el {time}"],
    "{count} archives could not be cached.": ["有 {count} 个代码包未能缓存。", "有 {count} 個程式碼包未能快取。", "{count} 個のパッケージをキャッシュできませんでした。", "패키지 {count}개를 캐시하지 못했습니다.", "No se pudieron guardar {count} paquetes en caché."],
    "Workshop unavailable; showing saved data.": ["工坊暂不可达，正在显示已保存的数据。", "工坊暫時無法連線，正在顯示已儲存的資料。", "工房に接続できないため保存済みデータを表示します。", "워크숍에 연결할 수 없어 저장된 데이터를 표시합니다.", "Taller no disponible; se muestran los datos guardados."],
    "Focus the game before enabling system input.": ["请将游戏置于前台后启用系统输入。", "請將遊戲置於前景後啟用系統輸入。", "システム入力を有効にする前にゲームを前面にしてください。", "시스템 입력 전에 게임을 전면에 두세요.", "Enfoca el juego antes de activar la entrada del sistema."],
    "Connect the Windows target before switching input mode.": ["请先连接目标窗口，再切换输入方式。", "請先連線目標視窗，再切換輸入方式。", "入力方式を切り替える前に対象ウィンドウに接続してください。", "입력 방식을 바꾸기 전에 대상 창에 연결하세요.", "Conecta la ventana de destino antes de cambiar el modo."],
    "Release all inputs before switching input mode.": ["请松开全部按键和鼠标按钮，再切换输入方式。", "請放開全部按鍵與滑鼠按鈕，再切換輸入方式。", "入力をすべて離してから切り替えてください。", "모든 키와 마우스 버튼을 놓은 후 전환하세요.", "Suelta todas las teclas y botones antes de cambiar el modo."],
    "Prevent the target window from moving the mouse": ["防止目标窗口移动鼠标", "防止目標視窗移動滑鼠", "対象ウィンドウによるマウス移動を防止", "대상 창의 마우스 이동 방지", "Evitar que la ventana de destino mueva el ratón"],
}


def sync():
    for path in sorted((ROOT / "i18n").glob("*/LC_MESSAGES/ok.po")):
        locale = path.parents[1].name
        catalog = polib.pofile(str(path))
        missing = []
        for source, translations in TEXT.items():
            if catalog.find(source) is None:
                translated = translations[LOCALES.index(locale)] if locale in LOCALES else source
                missing.append("\nmsgid " + json.dumps(source, ensure_ascii=False)
                               + "\nmsgstr " + json.dumps(translated, ensure_ascii=False) + "\n")
        if missing:
            with path.open("a", encoding="utf-8", newline="\n") as output:
                output.write("\n# Independent client\n" + "".join(missing))
        catalog = polib.pofile(str(path), check_for_duplicates=True)
        catalog.save_as_mofile(str(path.with_suffix(".mo")))
        print(f"{locale}: added {len(missing)} entries")


if __name__ == "__main__":
    sync()
