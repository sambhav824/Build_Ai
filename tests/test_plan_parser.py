import os
import cv2
import numpy as np
import pytest
from design.plan_parser import PlanParser
from agents.design_agent.design_agent import DesignAgent
from api.schemas.protocol import AgentRequest

@pytest.fixture(scope="module")
def sample_blueprint_image(tmp_path_factory):
    # Create synthetic 2D blueprint image with dark walls on light background
    img_dir = tmp_path_factory.mktemp("blueprints")
    img_path = os.path.join(str(img_dir), "synthetic_blueprint.png")

    img = np.ones((600, 800, 3), dtype=np.uint8) * 245 # Light grey background

    # Draw outer perimeter walls (dark line)
    cv2.rectangle(img, (80, 80), (720, 520), (20, 20, 20), thickness=6)

    # Draw interior partition walls
    cv2.line(img, (400, 80), (400, 520), (20, 20, 20), thickness=4)
    cv2.line(img, (80, 300), (400, 300), (20, 20, 20), thickness=4)
    cv2.line(img, (400, 320), (720, 320), (20, 20, 20), thickness=4)

    cv2.imwrite(img_path, img)
    return img_path

def test_plan_parser_contour_extraction(sample_blueprint_image):
    res = PlanParser.parse_image_plan(sample_blueprint_image, scale_pixels_per_foot=18.0)
    assert res is not None
    assert "extracted_rooms" in res
    assert len(res["extracted_rooms"]) >= 3
    assert res["scale_pixels_per_foot"] == 18.0

    for room in res["extracted_rooms"]:
        assert room["w"] > 0
        assert room["h"] > 0
        assert "confidence" in room

def test_design_agent_mode_b_uploaded_plan(sample_blueprint_image):
    agent = DesignAgent()
    req = AgentRequest(
        project_id="BS-UPLOAD-001",
        execution_id="EXEC-UPL-01",
        agent="design_agent",
        action="upload_and_parse_plan",
        input={"image_path": sample_blueprint_image}
    )

    resp = agent.process(req)
    assert resp.status == "completed"
    assert resp.result["mode"] == "MODE_B_UPLOADED_DRAWING"
    assert "extracted_rooms" in resp.result
    assert "model_3d_obj" in resp.result
    assert os.path.exists(resp.result["model_3d_obj"])
