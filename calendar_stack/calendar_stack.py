from typing import Any, Generator, List, Optional, Type, TypeVar,  cast, Iterator, Set
import sys
import random
import argparse
from operator import attrgetter, itemgetter
import attr, cattr
import itertools as it
import yaml
import json
import networkx as nx
from collections import defaultdict

G = nx.Graph()

T = TypeVar("T")

def copyas(obj: T, **kwargs) -> T:
    return obj.__class__(**{**attr.asdict(obj), **kwargs})

@attr.define(frozen=True)
class Event:
    name: str
    time: str
    duration: str
    priority: int = 0
    color: Optional[str] = None
    id: Optional[str] = None
    uid: float = random.getrandbits(128)
    widthFactor: Optional[int] = None
    position: Optional[int] = None

    def set_width(self, width: int):
        return copyas(self, widthFactor=width)

@attr.define
class Day:
    day: int
    month: int
    year: int
    events: List[Event]

@attr.define
class ScheduleConfig:
    startTime: int
    endTime: int
    days: List[Day]

@attr.define
class SiteConfig:
    schedule: ScheduleConfig

def make_graph(events: List[Event]):
    G = nx.Graph()
    G.add_nodes_from(events, widthFactor=[], position=-1)
    for a, b in it.combinations(events, 2):
        a_start, a_dur, b_start, b_dur, *_ = [to_hr_float(x) for x in [
            a.time, a.duration, b.time, b.duration
        ]]
        if overlap(a_start, a_start + a_dur, b_start, b_start + b_dur):
            G.add_edge(a, b)
    return G

def to_hr_float(time: str):
    hr, min = time.split(":")
    return int(hr) + (int(min) / 60)

def overlap(a_start: float, a_end: float, b_start: float, b_end: float):
    return max(
        max(a_end - b_start, 0) - max(a_start - b_start, 0) - max(a_end - b_end, 0), 
        0
    )

def read_yaml(name: str):
    with open(name, 'r') as file:
        return yaml.safe_load(file)


def get_overlapping_components(G: nx.Graph):
    cliques = list(cast(Generator[List[Event], None, None], nx.find_cliques(G)))
    for clique in cliques:
        size = len(clique)
        for event in clique:
            width = G.nodes[event]["widthFactor"] + [size]
            G.add_node(event, widthFactor=width)
    
    num_widths = lambda event: len(set(G.nodes[event]["widthFactor"]))

    
    grouped = [(i, [*group]) for i, group in it.groupby(G.nodes, num_widths)]
    ranked_events = [
        cast(Set[Event], set(events)) for _, events in
        sorted(grouped, key=itemgetter(0), reverse=True)
    ]

    for clique in cliques:
        clique_s = set(clique)
        sort_by_priority = lambda events: sorted(
            events, 
            key=attrgetter("priority"), 
            reverse=True
        )
        ranked_clique = [*it.chain(*[
            sort_by_priority(clique_s & events) for events in ranked_events
        ])]
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
        yield copyas(cast(Event, event), **data)


def main(args: List[str]):
    parser = argparse.ArgumentParser()
    parser.add_argument("input")
    parser.add_argument("--output", "-o", required=False)
    parsed = parser.parse_args(args)

    config = cast(SiteConfig, cattr.structure(read_yaml(parsed.input), SiteConfig))
    graphs = [make_graph(day.events) for day in config.schedule.days]
    ordered = [get_overlapping_components(G) for G in graphs]
    days = [
        attr.asdict(copyas(day, events=list(events)))
        for day, events in zip(config.schedule.days, ordered)
    ]
    
    if parsed.output:
        with open('calendar.json', 'w') as file:
            json.dump(days, file)
    else:
        print(json.dumps(days))
    return 0

if __name__ == "__main__":
    exit(main(sys.argv[1:]))