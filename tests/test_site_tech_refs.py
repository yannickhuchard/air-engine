"""Exact identifiers stay in the generated page but are hidden until the reader shows them."""
from air.architecture_site import TECH_SWITCH, shell, tech_refs

DIGEST = 'sha256:' + 'ab' * 32


def test_visible_identifiers_are_wrapped_and_kept():
    html = tech_refs('<p>Baseline <code>urn:asteria:baseline:sav</code>, empreinte <code>' + DIGEST + '</code>.</p>'
                     '<a href="objects.html#n1" title="urn:keep:attribute">urn:asteria:req:1</a><p>champ <code>/body/links/0</code></p>')
    assert '<span class="tech-ref">urn:asteria:baseline:sav</span><span class="tech-alt">identifiant</span>' in html
    assert '<span class="tech-ref">' + DIGEST + '</span><span class="tech-alt">masquée</span>' in html, 'the label already names the digest'
    assert tech_refs('<p>Lot <code>' + DIGEST + '</code></p>').count('<span class="tech-alt">empreinte</span>') == 1
    assert '<span class="tech-ref">/body/links/0</span><span class="tech-alt">sélecteur</span>' in html
    assert 'title="urn:keep:attribute"' in html and '<span class="tech-ref">urn:asteria:req:1</span>' in html


def test_scripts_sources_options_and_svg_keep_their_bytes():
    untouched = ('<script type="application/json" id="air-capsule">{"id":"urn:a:b"}</script><pre><code>urn:source:x</code></pre>'
                 '<select><option>urn:in:option</option></select><svg><title>urn:in:svg</title><text>urn:in:svg</text></svg>')
    assert tech_refs(untouched) == untouched


def test_shell_offers_the_switch_and_masks_body_identifiers():
    page = shell('Titre', '<p><code>urn:asteria:x</code></p><script type="application/json" id="j">"urn:asteria:x"</script>', 'Projet', '', '')
    assert TECH_SWITCH in page and 'id="air-tech"' in page and '<label class="tech-switch" for="air-tech">' in page
    assert '<span class="tech-ref">urn:asteria:x</span>' in page and '"urn:asteria:x"</script>' in page
