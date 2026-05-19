from scripts.classify_ci_changes import classify_paths


def test_edge_client_change_selects_only_edge_lane_and_image() -> None:
    result = classify_paths(["edge-client/src/edge_client/app.py"])

    assert result.app_changed is True
    assert result.edge_client_changed is True
    assert result.backend_changed is False
    assert result.frontend_admin_changed is False
    assert result.nginx_changed is False
    assert result.app_shared_changed is False
    assert result.image_names == "edge-client"


def test_shared_app_change_selects_all_images() -> None:
    result = classify_paths(["docker-compose.ci.yml"])

    assert result.app_changed is True
    assert result.app_shared_changed is True
    assert result.image_names == "backend,frontend-admin,edge-client,nginx"


def test_compose_override_change_selects_all_images() -> None:
    result = classify_paths(["docker-compose.edge.yml"])

    assert result.app_changed is True
    assert result.app_shared_changed is True
    assert result.image_names == "backend,frontend-admin,edge-client,nginx"


def test_app_workflow_change_is_app_shared_and_platform() -> None:
    result = classify_paths([".github/workflows/reusable-app-ci.yml"])

    assert result.app_changed is True
    assert result.app_shared_changed is True
    assert result.platform_changed is True
    assert result.image_names == "backend,frontend-admin,edge-client,nginx"


def test_ci_classifier_change_is_app_shared_and_platform() -> None:
    result = classify_paths(["scripts/classify_ci_changes.py"])

    assert result.app_changed is True
    assert result.app_shared_changed is True
    assert result.platform_changed is True
    assert result.image_names == "backend,frontend-admin,edge-client,nginx"


def test_infra_change_selects_infra_lane_only() -> None:
    result = classify_paths(["terraform/main.tf"])

    assert result.app_changed is False
    assert result.platform_changed is False
    assert result.infra_changed is True
    assert result.image_names == ""
