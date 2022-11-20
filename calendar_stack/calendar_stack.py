import argparse
import itertools as it
import json
import random
import sys
from operator import attrgetter, itemgetter
from typing import Generator, Optional, TypeVar, Union, cast

import attr
import cattr
import networkx as nx
import yaml

G = nx.Graph()

T = TypeVar("T")


@attr.define(frozen=True, kw_only=True)
class AbstractEvent:
    time: str
    duration: str
    priority: int = 0
    # Need a uid so that events with the same time, duration, and priority don't
    # collapse into each other when making the graph
    uid: float = attr.field(factory=lambda: random.getrandbits(128))


@attr.frozen
class EventPosition:
    widthFactor: Optional[int] = None
    position: Optional[int] = None


@attr.define
class Day:
    day: int
    month: int
    year: int
    events: list[AbstractEvent]


@attr.define
class ScheduleConfig:
    startTime: int
    endTime: int
    days: list[Day]


@attr.define
class SiteConfig:
    schedule: list[ScheduleConfig]


def make_graph(events: list[AbstractEvent]):
    G = nx.Graph()
    G.add_nodes_from(events, widthFactor=None, position=-1)
    for a, b in it.combinations(events, 2):
        a_start, a_dur, b_start, b_dur = [
            to_hr_float(x) for x in [a.time, a.duration, b.time, b.duration]
        ]
        if overlap(a_start, a_start + a_dur, b_start, b_start + b_dur):
            G.add_edge(a, b)
    return G


def to_hr_float(time: str):
    hr, min = time.split(":")
    return int(hr) + (int(min) / 60)


def overlap(a_start: float, a_end: float, b_start: float, b_end: float):
    return max(
        max(a_end - b_start, 0) - max(a_start - b_start, 0) - max(a_end - b_end, 0), 0
    )


def read_yaml(name: str):
    with open(name, "r") as file:
        return yaml.safe_load(file)


def get_overlapping_components(G: nx.Graph):
    cliques = list(cast(Generator[list[AbstractEvent], None, None], nx.find_cliques(G)))
    for clique in cliques:
        size = len(clique)
        for event in clique:
            if not G.nodes[event]["widthFactor"]:
                G.nodes[event]["widthFactor"] = []
            G.nodes[event]["widthFactor"].append(size)

    num_widths = lambda event: len(set(G.nodes[event]["widthFactor"]))

    grouped = [(i, [*group]) for i, group in it.groupby(G.nodes, num_widths)]
    ranked_events = [
        cast(set[AbstractEvent], set(events))
        for _, events in sorted(grouped, key=itemgetter(0), reverse=True)
    ]

    for clique in cliques:
        clique_s = set(clique)
        sort_by_priority = lambda events: sorted(
            events, key=attrgetter("priority"), reverse=True
        )
        ranked_clique = [
            *it.chain(
                *[sort_by_priority(clique_s & events) for events in ranked_events]
            )
        ]
        unranked = sort_by_priority(clique_s - set(ranked_clique))
        seen = set()
        positions = iter(range(len(clique)))
        for event in it.chain(ranked_clique, unranked):
            if (position := G.nodes[event]["position"]) == -1:
                while True:
                    position = next(positions)
                    if position not in seen:
                        break
            else:
                seen.add(position)
            G.nodes[event]["position"] = position

    for event, data in G.nodes.items():
        data["widthFactor"] = max(data["widthFactor"])
        yield EventPosition(**data)


def make_room_hashable(data: object, _):
    if isinstance(data, list):
        return tuple(data)
    return data


def main(args: list[str] | None = None):
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parsed = parser.parse_args(args)

    cattr.register_structure_hook(Union[str, list[str], None], make_room_hashable)
    config = cattr.structure(read_yaml(parsed.input), SiteConfig)
    graphs = [
        [make_graph(day.events) for day in schedule.days]
        for schedule in config.schedule
    ]

    print(
        json.dumps(
            [
                [
                    [attr.asdict(event) for event in get_overlapping_components(G)]
                    for G in schedule
                ]
                for schedule in graphs
            ]
        )
    )
    return 0


if __name__ == "__main__":
    exit(main(["../brainhack/config.yaml"]))
