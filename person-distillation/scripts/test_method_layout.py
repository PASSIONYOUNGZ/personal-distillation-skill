"""Method reading/provenance regressions; browser layout is checked separately."""
import copy
import unittest

from render_reader import render_methods
from test_reader_layout import Element, ReaderTree


def fixture():
    items={
        'first':{'id':'first','title':'First original','short':'First work'},
        'second':{'id':'second','title':'Second original'},
    }
    method={
        'id':'specific-method','title':'A concrete method','summary':'A bounded synthesis.',
        'steps':[
            {'title':'Choose a case','text':'Explain the initial choice.'},
            {'title':'Check the result','text':'Describe what was actually observed.'},
            {'title':'Adjust the next action','text':'Explain the resulting change.'},
        ],
        'boundary':'A condition that changes how the method applies.',
        'counterexamples':['A conflicting example must remain easy to see.'],
        'evidence':[
            {'item_id':'first','kind':'observed','note':'The observed first action.','locator':'frames 1–3'},
            {'item_id':'first','kind':'self_report','note':'The author described an outcome.','locator':'original lines 4–7'},
            {'item_id':'second','kind':'inference','note':'A limited comparison between cases.','locator':'original paragraph 2'},
        ],
    }
    return method,items


def visible_text(node):
    """Read the default native-details state without pretending to render CSS."""
    if not isinstance(node,Element):return node
    if node.tag=='details' and 'open' not in node.attrs:
        return ''.join(visible_text(child) for child in node.children
                       if isinstance(child,Element) and child.tag=='summary')
    return ''.join(visible_text(child) for child in node.children)


class MethodLayout(unittest.TestCase):
    def test_shared_source_is_one_default_entry_without_losing_evidence(self):
        method,items=fixture();before=copy.deepcopy(method)
        tree=ReaderTree(render_methods([method],items)).root
        sources=tree.descendants(cls='method-source-links')[0]
        self.assertEqual([node.attrs['href'] for node in sources.descendants(tag='a')],
                         ['#note-first','#note-second'])
        self.assertEqual(method,before)
        for entry in method['evidence']:
            self.assertIn(entry['note'],tree.text())
            self.assertIn(entry['locator'],tree.text())
            self.assertNotIn(entry['note'],visible_text(tree))
            self.assertNotIn(entry['locator'],visible_text(tree))

    def test_actions_conditions_and_counterexamples_are_not_hidden_with_sources(self):
        method,items=fixture();tree=ReaderTree(render_methods([method],items)).root
        visible=visible_text(tree)
        for step in method['steps']:
            self.assertIn(step['title'],visible)
            self.assertIn(step['text'],visible)
        self.assertIn(method['summary'],visible)
        self.assertIn(method['boundary'],visible)
        self.assertIn(method['counterexamples'][0],visible)
        steps=tree.descendants(cls='method-steps')[0]
        self.assertEqual(steps.tag,'ol')
        self.assertEqual(len(steps.descendants(tag='li')),3)
        disclosure=tree.descendants(cls='method-evidence-details')[0]
        self.assertNotIn('open',disclosure.attrs)
        self.assertIn('查看依据',disclosure.descendants(tag='summary')[0].text())

    def test_folded_provenance_still_escapes_untrusted_source_text(self):
        method,items=fixture()
        items['first']['short']='<img src=x onerror=alert(1)>'
        method['evidence'][0]['note']='<script>unsafe()</script>'
        method['evidence'][0]['locator']='file "A&B" <raw>'
        tree=ReaderTree(render_methods([method],items)).root
        self.assertFalse(tree.descendants(tag='script'))
        self.assertFalse(tree.descendants(tag='img'))
        self.assertIn(items['first']['short'],tree.text())
        self.assertIn(method['evidence'][0]['note'],tree.text())
        self.assertIn(method['evidence'][0]['locator'],tree.text())


if __name__=='__main__':unittest.main()
