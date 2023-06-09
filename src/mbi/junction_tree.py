import networkx as nx
import itertools
import numpy as np
from collections import OrderedDict


class JunctionTree:
    """ A JunctionTree is a transformation of a GraphicalModel into a tree structure.  It is used
        to find the maximal cliques in the graphical model, and for specifying the message passing
        order for belief propagation.  The JunctionTree is characterized by an elimination_order,
        which is chosen greedily by default, but may be passed in if desired.
    """

    def __init__(self, domain, cliques, elimination_order=None):
        self.cliques = [tuple(cl) for cl in cliques]
        self.domain = domain
        self.graph = self._make_graph()     # 构造图 属性为节点 度量属性为边
        self.tree, self.order = self._make_tree(elimination_order)

    def maximal_cliques(self):
        """ return the list of maximal cliques in the model """
        # return list(self.tree.nodes())
        return list(nx.dfs_preorder_nodes(self.tree))

    def mp_order(self):
        """ return a valid message passing order """
        edges = set()
        messages = [(a, b) for a, b in self.tree.edges()] + [(b, a) for a, b in self.tree.edges()]  # message按照正反顺序记录节点树中的边
        for m1 in messages:
            for m2 in messages:
                if m1[1] == m2[0] and m1[0] != m2[1]:   # 将节点树中的边替换为有向边添加消息
                    edges.add((m1, m2))
        G = nx.DiGraph()  # 生成有向图
        G.add_nodes_from(messages)  # 所有边作为节点，
        G.add_edges_from(edges)
        return list(nx.topological_sort(G))     # 拓扑排序输出消息传递的顺序

    def separator_axes(self):
        return {(i, j): tuple(set(i) & set(j)) for i, j in self.mp_order()}

    def neighbors(self):
        return {i: set(self.tree.neighbors(i)) for i in self.maximal_cliques()}

    def _make_graph(self):
        G = nx.Graph()
        G.add_nodes_from(self.domain.attrs)
        for cl in self.cliques:
            G.add_edges_from(itertools.combinations(cl, 2))
        return G

    def _triangulated(self, order):
        edges = set()
        G = nx.Graph(self.graph)
        for node in order:
            tmp = set(itertools.combinations(G.neighbors(node), 2))
            edges |= tmp
            G.add_edges_from(tmp)
            G.remove_node(node)
        tri = nx.Graph(self.graph)
        tri.add_edges_from(edges)


        cliques = [tuple(c) for c in nx.find_cliques(tri)]
        cost = sum(self.domain.project(cl).size() for cl in cliques)
        return tri, cost

    def _greedy_order(self, stochastic=True):   # 贪心算法给出消除变量的顺序
        order = []
        domain, cliques = self.domain, self.cliques
        unmarked = list(domain.attrs)   # 未标记的属性
        cliques = set(cliques)      # 最大团集合
        total_cost = 0
        for k in range(len(domain)):    # 基于属性数量开始循环
            cost = OrderedDict()
            for a in unmarked:
                # all cliques that have a
                neighbors = list(filter(lambda cl: a in cl, cliques))
                # variables in this "super-clique"
                variables = tuple(set.union(set(), *map(set, neighbors)))
                # domain for the resulting factor
                newdom = domain.project(variables)
                # cost of removing a
                cost[a] = newdom.size()

            # find the best variable to eliminate   贪心算法找出变量消除的最佳顺序
            if stochastic:
                choices = list(unmarked)
                costs = np.array([cost[a] for a in choices], dtype=float)
                probas = np.max(costs) - costs + 1
                probas /= probas.sum()
                i = np.random.choice(probas.size, p=probas)
                a = choices[i]
                # print(choices, probas)
            else:
                a = min(cost, key=lambda a: cost[a])

            # do some cleanup
            order.append(a)
            unmarked.remove(a)
            neighbors = list(filter(lambda cl: a in cl, cliques))
            variables = tuple(set.union(set(), *map(set, neighbors)) - {a})
            cliques -= set(neighbors)
            cliques.add(variables)
            total_cost += cost[a]

        return order, total_cost

    def _make_tree(self, order=None):
        if order is None:
            # orders = [self._greedy_order(stochastic=True) for _ in range(1000)]
            # orders.append(self._greedy_order(stochastic=False))
            # order = min(orders, key=lambda x: x[1])[0]
            order = self._greedy_order(stochastic=False)[0]
        self.elimination_order = order  # 给出变量消除的顺序
        tri, cost = self._triangulated(order)   # 对图进行三角化
        # cliques = [tuple(c) for c in nx.find_cliques(tri)]
        cliques = sorted([self.domain.canonical(c) for c in nx.find_cliques(tri)])
        complete = nx.Graph()
        complete.add_nodes_from(cliques)    # 图的节点为最大团中的每个团
        for c1, c2 in itertools.combinations(cliques, 2):
            wgt = len(set(c1) & set(c2))
            complete.add_edge(c1, c2, weight=-wgt)  # 添加团之间的边 并记录权重为交集大小
        spanning = nx.minimum_spanning_tree(complete)   # 将联结树变为最小生成树
        return spanning, order
