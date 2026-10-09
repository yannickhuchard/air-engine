"""Optional authoring cannot read outside the user-designated site."""
import importlib
from pathlib import Path
import pytest


def test_video_authoring_rejects_source_traversal(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    authoring=importlib.import_module('prepare_architecture_trailers')
    site=tmp_path/'site';site.mkdir();(site/'story.json').write_text('{}')
    (tmp_path/'private.json').write_text('private')
    assert authoring.site_file(site,'story.json')==site/'story.json'
    for relative in ['../private.json','a/../../private.json','C:/private.json','\\\\server\\private.json',str(tmp_path/'private.json')]:
        with pytest.raises(ValueError):authoring.site_file(site,relative)


def test_optional_authoring_preserves_existing_work(tmp_path, monkeypatch):
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]/'scripts'))
    authoring=importlib.import_module('prepare_architecture_trailers')
    (tmp_path/'site-manifest.json').write_text('{"dossiers":[]}')
    out=tmp_path/'reviewed';out.mkdir();(out/'brag-plan.md').write_text('human-edited plan')
    with pytest.raises(ValueError,match='existing authoring'):
        authoring.prepare(tmp_path,out,tmp_path,tmp_path)
    assert (out/'brag-plan.md').read_text()=='human-edited plan'
