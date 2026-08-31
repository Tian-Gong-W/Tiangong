from pathlib import Path


def _read(path: str) -> str:
    return Path(path).read_text(encoding="utf-8")


def test_react_tasks_expose_real_terminal_delete_control():
    tasks = _read("web/src/components/TasksListView.tsx")
    app = _read("web/src/App.tsx")

    assert "onDelete: (task: Task) => void" in tasks
    assert "task.status === 'completed' || task.status === 'failed'" in tasks
    assert "运行中或候审批任务不能删除" in tasks
    assert "onDelete={handleDeleteTask}" in app
    assert "/api/missions/${encodeURIComponent(task.id)}/delete" in app
    assert "Audit 审计日志保留" in app


def test_react_module_shell_has_vertical_scroll_host():
    app = _read("web/src/App.tsx")

    assert "flex-1 min-h-0 min-w-0 overflow-y-auto overflow-x-hidden overscroll-y-contain" in app
