from datetime import date

import pytest

from src.services.db_service import DatabaseService
from src.services.expense_service import ExpenseService
from src.services.machine_service import MachineService
from src.services.project_service import ProjectService
from src.services.user_service import UserService


def test_admin_sees_all_and_users_only_see_owned_business_data(tmp_path):
    DatabaseService(str(tmp_path / "permissions.db"))
    users = UserService()
    admin = users.create_user("admin", "admin123", "管理员", role="admin")
    first = users.create_user("first", "first123", "用户甲", role="user")
    second = users.create_user("second", "second123", "用户乙", role="user")

    first_projects = ProjectService(first)
    second_projects = ProjectService(second)
    admin_projects = ProjectService(admin)
    first_project = first_projects.create_project("甲的项目")
    second_project = second_projects.create_project("乙的项目")

    assert [item.name for item in first_projects.get_all_projects()] == ["甲的项目"]
    assert [item.name for item in second_projects.get_all_projects()] == ["乙的项目"]
    assert {item.name for item in admin_projects.get_all_projects()} == {"甲的项目", "乙的项目"}
    assert second_projects.get_project_by_id(first_project.id) is None

    first_machine = MachineService(first).create_machine(
        first_project.id, "10.20.1.10", business_ip="10.20.1.11"
    )
    second_machine = MachineService(second).create_machine(
        second_project.id, "10.20.2.10", business_ip="10.20.2.11"
    )
    assert [item.id for item in MachineService(first).get_all_machines()] == [first_machine.id]
    assert {item.id for item in MachineService(admin).get_all_machines()} == {
        first_machine.id, second_machine.id
    }
    with pytest.raises(ValueError, match="无权访问该项目"):
        MachineService(first).create_machine(
            second_project.id, "10.20.9.10", business_ip="10.20.9.11"
        )

    ExpenseService(first).create_expense(
        first_project.id, date(2026, 9, 11), "交通", "100"
    )
    ExpenseService(second).create_expense(
        second_project.id, date(2026, 9, 11), "交通", "200"
    )
    assert ExpenseService(first).get_profit_summary(None)["actual_cost"] == 100.0
    assert ExpenseService(admin).get_profit_summary(None)["actual_cost"] == 300.0
    assert ExpenseService(admin).get_profit_summary(None, owner_id=first.id)["actual_cost"] == 100.0
    assert ExpenseService(admin).get_profit_summary(None, owner_id=second.id)["actual_cost"] == 200.0
    assert MachineService(admin).get_machines_page(owner_id=first.id)[0] == 1
    assert MachineService(admin).get_machines_page(owner_id=second.id)[0] == 1
    assert ProjectService(admin).get_projects_page(owner_id=first.id)[0] == 1
    assert ProjectService(admin).get_projects_page(owner_id=second.id)[0] == 1
    all_dashboard = ProjectService(admin).get_dashboard_stats()
    first_dashboard = ProjectService(admin).get_dashboard_stats(owner_id=first.id)
    second_dashboard = ProjectService(admin).get_dashboard_stats(owner_id=second.id)
    assert all_dashboard["total_projects"] == 2
    assert all_dashboard["total_machines"] == 2
    assert all_dashboard["actual_cost_total"] == 300.0
    assert first_dashboard["total_projects"] == 1
    assert first_dashboard["total_machines"] == 1
    assert first_dashboard["actual_cost_total"] == 100.0
    assert second_dashboard["total_projects"] == 1
    assert second_dashboard["total_machines"] == 1
    assert second_dashboard["actual_cost_total"] == 200.0

    dashboard_rows = {
        row[0]: row
        for row in all_dashboard["user_summaries"]
    }
    assert dashboard_rows["用户甲（first）"][3:6] == [1, 1, 0]
    assert dashboard_rows["用户甲（first）"][6:9] == ["0.00", "100.00", "-100.00"]
    assert dashboard_rows["用户乙（second）"][3:6] == [1, 1, 0]
    assert dashboard_rows["用户乙（second）"][6:9] == ["0.00", "200.00", "-200.00"]
    assert ProjectService(first).get_dashboard_stats()["user_summaries"] == []


def test_admin_can_manage_users_and_ordinary_user_only_self_account(tmp_path):
    DatabaseService(str(tmp_path / "user-management.db"))
    service = UserService()
    admin = service.create_user("admin", "admin123", "管理员", role="admin")
    ordinary = service.create_user("ordinary", "ordinary123", "普通用户", role="user")
    other = service.create_user("other", "other123", "其他用户", role="user")

    service.update_user(
        other.id,
        actor=admin,
        display_name="已修改",
        role="admin",
        is_active=True,
    )
    updated = service.authenticate("other", "other123")
    assert updated.display_name == "已修改"
    assert updated.role == "admin"

    service.update_user(ordinary.id, actor=ordinary, display_name="我的新名称")
    assert service.authenticate("ordinary", "ordinary123").display_name == "我的新名称"
    with pytest.raises(ValueError, match="只能修改自己的账号"):
        service.update_user(other.id, actor=ordinary, display_name="越权修改")
    with pytest.raises(ValueError, match="不能修改用户名"):
        service.update_user(ordinary.id, actor=ordinary, role="admin")

    service.change_password(ordinary.id, "ordinary123", "ordinary456", actor=ordinary)
    assert service.authenticate("ordinary", "ordinary456") is not None
    with pytest.raises(ValueError, match="只能修改自己的账号"):
        service.change_password(other.id, "other123", "other456", actor=ordinary)

    service.delete_user(other.id, actor=admin)
    assert service.authenticate("other", "other123") is None
    with pytest.raises(ValueError, match="只有系统管理员"):
        service.delete_user(ordinary.id, actor=ordinary)
    with pytest.raises(ValueError, match="只有系统管理员"):
        service.list_users(actor=ordinary)
    with pytest.raises(ValueError, match="只有系统管理员"):
        service.create_user("blocked", "blocked123", "被拒绝", actor=ordinary)
    with pytest.raises(ValueError, match="只有系统管理员"):
        service.set_active(ordinary.id, False, actor=ordinary)
