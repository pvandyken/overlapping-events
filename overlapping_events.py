from typing import List, Type, TypedDict, cast, Iterator, Set
import itertools as it
import yaml
import json
import networkx as nx
from collections import defaultdict

G = nx.Graph()

class Event(TypedDict):
    name: str
    time: str
    duration: str

class Day(TypedDict):
    day: int
    month: int
    year: int
    events: List[Event]

class ScheduleConfig(TypedDict):
    startTime: int
    endTime: int
    days: List[Day]

class SiteConfig(TypedDict):
    schedule: ScheduleConfig

def make_graph(events: List[Event]):
    G = nx.Graph()
    enumed = list(enumerate(events))
    G.add_nodes_from(enumed)
    for (a_i, a), (b_i, b) in it.combinations(enumed, 2):
        a_start, a_dur, b_start, b_dur, *_ = [to_hr_float(x) for x in [
            a['time'], a['duration'], b['time'], b['duration']
        ]]
        if overlap(a_start, a_start + a_dur, b_start, b_start + b_dur):
            G.add_edge(a_i, b_i)
    return G

def to_hr_float(time: str):
    hr, min = time.split(":")
    return int(hr) + (int(min) / 60)

def overlap(a_start: float, a_end: float, b_start: float, b_end: float):
    return max(max(a_end - b_start, 0) - max(a_start - b_start, 0) - max(a_end - b_end, 0), 0)

def read_yaml(name: str):
    with open(name, 'r') as file:
        return yaml.safe_load(file)


def get_overlapping_components(G: nx.Graph):
    cliques = nx.find_cliques(G)
    sorted_cliques = defaultdict(list)
    for size, clique in it.groupby(cliques, len):
        sorted_cliques[size-1].extend(it.chain(*clique))
    subgraphs = [0]*len(sorted_cliques)
    for size, clique in sorted_cliques.items():
        subgraphs[size] = nx.subgraph(G, clique)
    return [nx.connected_components(sub_G) for sub_G in subgraphs]

def get_event_info(G: nx.Graph, components: List[Iterator[Set]]):
    events = defaultdict(list)
    for i, size in enumerate(components):
        group = it.chain(*size)
        for _, data in G.subgraph(group).nodes(data=True):
            events[i].append(data)
    return events


def main():
    config = cast(SiteConfig, read_yaml('config.yaml'))
    graphs = [make_graph(day['events']) for day in config['schedule']['days']]
    components = [get_overlapping_components(G) for G in graphs]
    days = []
    for day, G, events in zip(config['schedule']['days'], graphs, components):
        day = {
            "day": day['day'],
            "month": day['month'],
            "year": day['year'],
            "events": get_event_info(G, events)
        }
        days.append(day)
    with open('calendar.json', 'w') as file:
        json.dump(days, file)

if __name__ == "__main__":
    main()