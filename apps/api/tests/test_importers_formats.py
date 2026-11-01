"""Annotation importers: CVAT for Images XML and Label Studio JSON."""
import json

from app.services import importers

CVAT_XML = """<?xml version="1.0" encoding="utf-8"?>
<annotation>
  <version>1.1</version>
  <image id="0" name="site_a.jpg" width="200" height="100">
    <box label="หมวกนิรภัย" xtl="10" ytl="20" xbr="60" ybr="70"/>
    <polygon label="safety vest" points="100,10;150,10;150,60;100,60"/>
  </image>
</annotation>
"""

CVAT_NO_SIZE_XML = """<annotation>
  <image name="raw.png">
    <box label="helmet" xtl="10" ytl="5" xbr="30" ybr="25"/>
  </image>
</annotation>
"""

LS_TASKS = [
    {
        "id": 1,
        "data": {"image": "https://cdn.example.com/media/frame_001.jpg?sig=abc#frag"},
        "annotations": [
            {
                "result": [
                    {"type": "rectanglelabels", "original_width": 100, "original_height": 100,
                     "value": {"x": 10, "y": 20, "width": 30, "height": 40,
                               "labels": ["helmet", "safety vest"]}},
                    {"type": "polygonlabels", "original_width": 100, "original_height": 100,
                     "value": {"points": [[10, 10], [50, 10], [50, 50]], "labels": ["vest"]}},
                    {"type": "brushlabels", "original_width": 100, "original_height": 100,
                     "value": {"rle": [1, 2, 3], "labels": ["mask"]}},
                    {"type": "keypointlabels", "original_width": 100, "original_height": 100,
                     "value": {"x": 5, "y": 5, "labels": ["nose"]}},
                ]
            }
        ],
    },
    {"id": 2, "data": {"image": "frame_001.jpg"}, "annotations": []},
]

COCO_JSON = {
    "images": [{"id": 1, "file_name": "c1.jpg", "width": 100, "height": 50}],
    "annotations": [{"id": 1, "image_id": 1, "category_id": 1, "bbox": [10, 5, 20, 10]}],
    "categories": [{"id": 1, "name": "hat"}],
}


def test_cvat_xml_routes_to_cvat_and_normalizes():
    b = importers.collect([("ann.xml", CVAT_XML.encode())])

    assert b.voc == {}
    assert list(b.cvat) == ["site_a.jpg"]

    got = importers.annotations_for(b, "train/images/site_a.jpg", 200, 100)
    assert got[0] == ("หมวกนิรภัย", {"kind": "bbox", "x": 0.05, "y": 0.2, "w": 0.25, "h": 0.5})
    assert got[1][0] == "safety vest"
    assert got[1][1]["kind"] == "polygon"
    assert got[1][1]["points"] == [0.5, 0.1, 0.75, 0.1, 0.75, 0.6, 0.5, 0.6]


def test_cvat_image_without_size_falls_back_to_actual_size():
    b = importers.collect([("ann.xml", CVAT_NO_SIZE_XML.encode())])

    assert importers.annotations_for(b, "raw.png", 100, 50) == [
        ("helmet", {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.4})
    ]


def test_label_studio_json_rectangle_and_polygon():
    b = importers.collect([("project.json", json.dumps(LS_TASKS).encode())])

    assert b.coco == {}
    assert list(b.ls) == ["frame_001.jpg"]

    got = importers.annotations_for(b, "bucket/frame_001.jpg", 640, 480)
    assert got == [
        ("helmet", {"kind": "bbox", "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}),
        ("safety vest", {"kind": "bbox", "x": 0.1, "y": 0.2, "w": 0.3, "h": 0.4}),
        ("vest", {"kind": "polygon", "points": [0.1, 0.1, 0.5, 0.1, 0.5, 0.5]}),
    ]


def test_label_studio_accepts_wrapped_tasks_key():
    b = importers.collect([("project.json", json.dumps({"tasks": LS_TASKS}).encode())])
    assert list(b.ls) == ["frame_001.jpg"]


def test_coco_json_still_parses_as_coco():
    b = importers.collect([("coco.json", json.dumps(COCO_JSON).encode())])

    assert list(b.coco) == ["c1.jpg"]
    assert b.ls == {}
    assert importers.annotations_for(b, "c1.jpg", 100, 50) == [
        ("hat", {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.2})
    ]


def test_malformed_label_studio_json_is_ignored():
    b = importers.collect([("bad.json", b'[{"data": {}}]')])

    assert b.ls == {} and b.coco == {}
    assert b.has_annotations is False


def test_has_annotations_covers_new_formats():
    assert importers.collect([("ann.xml", CVAT_XML.encode())]).has_annotations is True
    assert importers.collect([("project.json", json.dumps(LS_TASKS).encode())]).has_annotations is True


VOC_XML = """<annotation>
  <object><name>helmet</name><bndbox><xmin>10</xmin><ymin>5</ymin><xmax>30</xmax><ymax>25</ymax></bndbox></object>
</annotation>
"""


def test_voc_xml_still_routes_to_voc():
    b = importers.collect([("a.xml", VOC_XML.encode())])
    assert b.cvat == {}
    assert importers.annotations_for(b, "train/a.jpg", 100, 50) == [
        ("helmet", {"kind": "bbox", "x": 0.1, "y": 0.1, "w": 0.2, "h": 0.4})
    ]


def test_yolo_txt_still_uses_class_names():
    b = importers.collect([("classes.txt", b"helmet\nvest\n"), ("a.txt", b"0 0.5 0.5 0.2 0.2\n")])
    assert importers.annotations_for(b, "a.jpg", 100, 100) == [
        ("helmet", {"kind": "bbox", "x": 0.4, "y": 0.4, "w": 0.2, "h": 0.2})
    ]


def test_invalid_utf8_json_is_ignored_not_crashing():
    b = importers.collect([("bad.json", b'{"a": "\xff"}')])
    assert b.coco == {} and b.ls == {} and b.has_annotations is False
