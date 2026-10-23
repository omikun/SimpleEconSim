"""Full checkpoints for the native desktop world, including the Egypt campaign.

Uses the same verified state/trace pair and branch recovery as SimServer. Only
named rendering resources are recreated; unknown unpicklable state fails the
save instead of being silently dropped. These are trusted local artifacts.
"""
import importlib
import threading

from simulation_checkpoint import save, restore


RENDER_RESOURCES = frozenset({
    '_micropoly_gpu_renderer', '_terrain_renderer', '_ui_map_label_surface',
    '_map_label_target', '_ui_map_surface', '_cached_topo_surface',
    '_scaled_terrain_surface', '_cached_border_overlay',
})


class NativeSimulation:
    def __init__(self, world, engine_module='worldview_engine'):
        if engine_module not in ('worldview_engine', 'client.desktop.engine'):
            raise ValueError('unsupported native simulation engine')
        self.world = world
        self.engine_module = engine_module
        self._lock = threading.RLock()

    @property
    def tiles(self):
        return self.world['tiles']

    @property
    def turn(self):
        return self.world['turn']

    @property
    def run_trace(self):
        return self.world.get('run_trace')

    def step(self):
        with self._lock:
            return importlib.import_module(self.engine_module).step_world(self.world)

    def __getstate__(self):
        return {'world': self.world, 'engine_module': self.engine_module}

    def __setstate__(self, state):
        self.__dict__.update(state)
        self._lock = threading.RLock()
        self.world['playing'] = False


def save_world(world, directory, *, engine_module='worldview_engine'):
    """Save the native graph after closing any pending between-turn actions."""
    from trace_snapshots import sample, record
    simulation = NativeSimulation(world, engine_module)
    session = world.get('_trace_session')
    if simulation.run_trace is None or session is None:
        raise ValueError('a native causal checkpoint requires an enabled recorder')
    if (session.run_trace.count != session.pending_start
            or sample(session.tiles, session.nations) != session._trace_previous):
        record(session)
    # Scenario debt objects also reference this exact world dictionary. Keep its
    # identity so those aliases survive; copying only the outer dictionary would
    # serialize a second world through those links, including live GPU resources.
    with simulation._lock:
        resources = {key: world.pop(key) for key in RENDER_RESOURCES if key in world}
        try:
            return save(simulation, directory)
        finally:
            world.update(resources)


def restore_world(manifest_path, branch_directory):
    simulation = restore(manifest_path, branch_directory)
    if not isinstance(simulation, NativeSimulation):
        raise ValueError('checkpoint contains a server simulation, not a native world')
    return simulation.world
