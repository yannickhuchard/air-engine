"""A portable question, without a connection, credentials, or automatic publication."""
from html import escape
import json
from air import editorial, question_capsule
from air.deliverables import mid


def H(value):
    return escape(editorial.prose(value), quote=True)


def page(reading, namespace):
    pin = reading['baseline']
    defaults = []
    for q in reading['questions']:
        sources = [s['reference'] for s in q['sources'][:64]]
        capsule = question_capsule.make(pin, namespace, q['id'], q['question'], 'solution', sources)
        defaults.append((q['id'], {'capsule': capsule}))
    body = '<nav class="breadcrumb"><a href="index.html">Dossier</a> / Coopération</nav><h1>Travailler avec un assistant</h1><p class="intro">Emportez une question et ses sources exactes dans votre prochaine conversation.</p>'
    body += '<ol class="capsule-steps"><li><strong>Choisir</strong><span>Une question et les sources utiles.</span></li><li><strong>Transmettre</strong><span>La capsule, au destinataire autorisé.</span></li><li><strong>Vérifier</strong><span>Le contexte dans AIR avant de travailler.</span></li></ol>'
    body += '<p>La préparation reste dans cette page. Aucun assistant ni serveur AIR n’est contacté ; aucune copie n’est enregistrée automatiquement. Le téléchargement contient des métadonnées internes, à partager dans le périmètre autorisé.</p>'
    body += '<details class="capsule-context"><summary>Vérifier le dossier que je transmets</summary><p>Namespace <code>' + H(namespace) + '</code></p><p>Baseline <code>' + H(pin['id']) + '</code> · r' + str(pin['revision']) + '</p><p class="digest"><code>' + H(pin['digest']) + '</code></p><p>La capsule conserve ces références. Un logo ou un nom identique ne garantit pas le même registre.</p></details>'
    body += '<div id="capsule-editor" hidden><label for="capsule-topic">Sujet de la question</label><select id="capsule-topic">' + ''.join('<option value="' + q['id'] + '">' + q['id'] + ' · ' + H(q['question']) + '</option>' for q in reading['questions']) + '</select><p class="capsule-help">Changer de sujet remplace la question et la sélection de sources.</p>'
    body += '<label for="capsule-audience">Pour quel public ?</label><select id="capsule-audience">' + ''.join('<option value="' + r['id'] + '"' + (' selected' if r['id'] == 'solution' else '') + '>' + H(r['label']) + '</option>' for r in reading['roles']) + '</select><label for="capsule-question">Votre question</label><textarea id="capsule-question" maxlength="2000" rows="4"></textarea><fieldset><legend>Sources à joindre, au plus 64</legend><p>La sélection ne prouve pas que ces sources suffisent à répondre.</p><details class="capsule-source-picker"><summary>Choisir ou lire les sources jointes</summary><div id="capsule-sources"></div></details></fieldset>'
    body += '<div class="capsule-actions"><button type="button" id="capsule-download">Télécharger la capsule JSON</button><button type="button" id="capsule-copy">Copier la demande pour l’assistant</button></div><p id="capsule-status" role="status" aria-live="polite"></p><details><summary>Lire la demande avant de la transmettre</summary><label for="capsule-prompt">Demande et capsule</label><textarea id="capsule-prompt" rows="12" readonly></textarea></details></div>'
    body += '<p id="capsule-unavailable">Sans l’éditeur interactif, les capsules de départ sont disponibles ci-dessous. Vous pouvez les modifier avec votre agent, qui doit recalculer leur empreinte puis vérifier le contexte.</p><details><summary>Télécharger une capsule de départ par sujet</summary><ul>' + ''.join('<li><a download href="question-' + q['id'] + '.json">' + H(q['question']) + '</a>' + (' · sélection limitée aux 64 premières sources' if len(q['sources']) > 64 else '') + '</li>' for q in reading['questions']) + '</ul></details>'
    body += '<section><h2>Dans ChatGPT, Claude ou votre IDE</h2><p>Joignez la capsule ou collez la demande dans un client déjà connecté au bon AIR. Appelez <code>air_whoami</code>, <code>air_capabilities</code>, puis <code>air_resume_question</code> avec cette capsule. Si l’outil manque ou refuse un identifiant, conservez le diagnostic et vérifiez le connecteur.</p><p>Une connexion ou un import dans ces produits n’est pas lancé par ce site. Un reçu vérifié décrit le contexte observé ; il n’est ni signé ni une autorisation de modification.</p><h3>Reprendre dans une autre conversation</h3><p>Conservez ensemble la capsule et le reçu retourné. Présentez le reçu comme <code>previous_receipt</code> lors de la prochaine reprise. AIR vérifiera de nouveau l’identité, la politique, la baseline et les sources. Un changement de client ou d’installation doit être diagnostiqué avant de poursuivre.</p><h3>Passer de la question à un changement</h3><p>Discuter les manques, préparer et valider les brouillons, puis effectuer le rebase. Joindre son <code>prepared_change</code> à la reprise pour contrôler son auteur et sa baseline. Le dépôt et la fermeture restent des appels explicites avec leurs propres vérifications. Après fermeture, produire la nouvelle capsule et régénérer les livrables.</p><p><a href="handoff.html">Préparer les échanges avec les équipes</a> · <a href="questions.html">Revenir aux réponses du dossier</a></p></section>'
    data = {'namespace': namespace, 'reading': reading,
            'links': {s['reference']['id'] + ':' + str(s['reference']['revision']):
                      'objects.html#' + mid(s['reference']['id'] + ':' + str(s['reference']['revision']))
                      for q in reading['questions'] for s in q['sources']}}
    body += '<script type="application/json" id="air-capsule">' + json.dumps(data, ensure_ascii=False, separators=(',', ':')).replace('<', '\\u003c').replace('>', '\\u003e').replace('&', '\\u0026') + '</script><script defer src="../../assets/capsule.js"></script>'
    return body, defaults
