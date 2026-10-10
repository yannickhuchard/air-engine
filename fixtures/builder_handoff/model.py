"""Two fictional builder teams; assignments are declarations, not human acceptance."""
import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location('handoff_build_fixture', Path(__file__).parents[1] / 'build_design/model.py')
build = importlib.util.module_from_spec(spec); spec.loader.exec_module(build)


def with_teams(objects):
    result = list(objects)
    for side in ('provider', 'consumer'):
        roles = []
        for duty in ('R', 'A'):
            name = side + '-' + duty
            result.append(build.obj('Role', name, {'responsibilities': ['Réaliser le périmètre' if duty == 'R' else 'Répondre du périmètre'], 'required_competencies': []}))
            result.append(build.obj('RaciAssignment', name + '-assignment', {'activity': 'Construire ' + side, 'phase': 'DELIVERY',
                'role': build.ref(name), 'responsibility': duty, 'subject': build.ref(side + '-unit')}))
            roles.append(build.ref(name))
        result.append(build.obj('OrganizationUnit', side + '-team', {'mandate': 'Équipe fictive ' + side, 'roles': roles}))
    return result
