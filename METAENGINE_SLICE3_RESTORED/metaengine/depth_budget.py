from __future__ import annotations

class DepthBudgetController:
    """Adaptive deep-compute budget.

    Budget is a safety ceiling, not the primary stopping rule.  The controller first asks whether
    the latest round changed the causal problem-space; only if useful change remains does hard
    budget exhaustion become the reason to stop.
    """
    def __init__(self, complexity):
        c=max(0.0,min(1.0,float(complexity)))
        # Enough headroom for one diagnostic-deep round plus a genuinely discriminating follow-up.
        # Later rounds must earn continuation through marginal gain.
        self.total=round(12.0+9.0*c,2)
        self.remaining=self.total
        self.last_spent=0.0
        self.low_gain_streak=0

    def next_budget(self, round_index):
        caps={1:6.4,2:4.4,3:2.8,4:1.8}
        return round(min(self.remaining,caps.get(round_index,1.5)),2)

    def consume(self, amount):
        self.last_spent=max(0.0,float(amount))
        self.remaining=max(0.0,self.remaining-self.last_spent)

    def evaluate(self,current,previous=None):
        if previous is None:
            gain=1.0
            components={'new_types':1.0,'new_peer_pairs':1.0,'causal_depth_gain':1.0,'tension_reduction':0.0,'topology_change':0.0,'productive_reground':1.0}
        else:
            nt=set(current.get('transformation_types',[]))-set(previous.get('transformation_types',[]))
            np=set(tuple(x) for x in current.get('peer_pairs',[]))-set(tuple(x) for x in previous.get('peer_pairs',[]))
            depth_delta=max(0,current.get('causal_depth',0)-previous.get('causal_depth',0))
            tension=max(0,previous.get('unresolved_tensions',0)-current.get('unresolved_tensions',0))
            topo=max(0,current.get('topology_mutation_edges',0)-previous.get('topology_mutation_edges',0))
            reg=max(0,current.get('source_reground_count',0)-previous.get('source_reground_count',0))
            # Regrounding only counts strongly when it participates in a new causal distinction.
            productive_reg=min(1.0,reg/4)*(1.0 if (nt or np or depth_delta or tension or topo) else .15)
            components={
                'new_types':min(1.0,len(nt)/4),
                'new_peer_pairs':min(1.0,len(np)/8),
                'causal_depth_gain':min(1.0,depth_delta/2),
                'tension_reduction':min(1.0,tension/2),
                'topology_change':min(1.0,topo),
                'productive_reground':productive_reg,
            }
            gain=min(1.0,.24*components['new_types']+.16*components['new_peer_pairs']+.28*components['causal_depth_gain']+.14*components['tension_reduction']+.10*components['topology_change']+.08*components['productive_reground'])

        efficiency=gain/max(.75,self.last_spent or 1.0)
        if previous is not None and gain<.16:
            self.low_gain_streak+=1
        else:
            self.low_gain_streak=0

        proliferation=current.get('node_count',0)>220 and gain<.18
        echo=previous is not None and gain<.075
        marginal=previous is not None and (gain<.20 or efficiency<.055)
        # Epistemic stopping has priority over hard budget exhaustion.
        if proliferation:
            stop='STOP_PROLIFERATION'
        elif echo:
            stop='STOP_RECURSIVE_ECHO'
        elif marginal:
            stop='STOP_MARGINAL_GAIN'
        elif self.remaining<.75:
            stop='STOP_BUDGET_EXHAUSTED'
        else:
            stop='CONTINUE'
        return {
            'realized_marginal_gain':round(gain,4),
            'structural_marginal_gain_diagnostic':round(gain,4),
            'eligible_for_policy_learning':False,
            'gain_per_cost_unit':round(efficiency,4),
            'gain_components':{k:round(v,4) for k,v in components.items()},
            'low_gain_streak':self.low_gain_streak,
            'stop_decision':stop,
            'remaining_budget':round(self.remaining,3),
            'policy':'CONTINUE_ONLY_WHEN_CAUSALLY_NEW_DISTINCTION_CONTRADICTION_EVIDENCE_DEPENDENCY_OPERATOR_PARSE_TOPOLOGY_REGROUND_OR_UNCERTAINTY_REDUCTION_JUSTIFIES_COST'
        }
