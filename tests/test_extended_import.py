from pathlib import Path
import tempfile
import unittest
import zipfile
import xml.etree.ElementTree as ET
from coach.score_import import read_ranked, root_from_file
from coach.musicxml import write
from coach.model import Pitch, Score, Note
from coach.harmony import identify
from coach.checker import constraints_for, check
from coach.review import canonical_label, review_harmony
from coach.pdf_export import annotated_xml
from examples.make_examples import example


class ExtendedImportTests(unittest.TestCase):
    def make_chord_score(self, path):
        write(example(),path)
        root=ET.parse(path).getroot()
        parts=root.findall('part')
        # Four explicit lines become two staves, each with a simultaneous two-note chord.
        for kept,other in ((parts[0],parts[1]),(parts[3],parts[2])):
            for measure,other_measure in zip(kept.findall('measure'),other.findall('measure')):
                note=other_measure.find('note')
                note.insert(0,ET.Element('chord'))
                measure.append(note)
        root.remove(parts[1]);root.remove(parts[2])
        for part in root.findall('part'):
            for i in range(5,11):
                measure=ET.SubElement(part,'measure',number=str(i))
                note=ET.SubElement(measure,'note');ET.SubElement(note,'rest',measure='yes')
                ET.SubElement(note,'duration').text='4'
        ET.ElementTree(root).write(path,encoding='utf-8',xml_declaration=True)

    def test_compressed_score_pitch_order_and_silent_tail(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'score.xml';compressed=Path(folder)/'score.mxl'
            self.make_chord_score(source)
            with zipfile.ZipFile(compressed,'w') as z:
                z.writestr('META-INF/container.xml','<container><rootfiles><rootfile full-path="score.xml"/></rootfiles></container>')
                z.write(source,'score.xml')
            score,labels,scope=read_ranked(compressed)
            self.assertEqual(len(score.measures),4)
            self.assertEqual(scope['input_measures'],10)
            self.assertEqual(scope['trailing_empty_measures'],['5','6','7','8','9','10'])
            first=next(score.frames())[1]
            self.assertEqual([str(first[v].pitch) for v in ('B','T','A','S')],['C3','C4','E4','G4'])

    def test_annotation_preserves_chord_group_onset_and_original_pitches(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'score.xml';target=Path(folder)/'annotated.xml'
            self.make_chord_score(source)
            score,_,_=read_ranked(source)
            findings=check(score,constraints_for(score))
            annotated_xml(source,target,findings,score=score)
            self.assertEqual(read_ranked(target)[0],score)
            root=ET.parse(target).getroot()
            # No direction may split the two adjacent members of a source chord.
            for measure in root.findall('part/measure'):
                children=list(measure)
                for index,child in enumerate(children):
                    if child.tag=='note' and child.find('chord') is not None:
                        self.assertEqual(children[index-1].tag,'note')

    def test_paradigm_bracket_ends_at_the_selected_final_sonority(self):
        with tempfile.TemporaryDirectory() as folder:
            source=Path(folder)/'score.xml';target=Path(folder)/'annotated.xml'
            self.make_chord_score(source)
            score,_,_=read_ranked(source)
            soprano=[n for n in score.notes if n.voice=='S']
            marks=[{'anchor':soprano[0].id,'end_anchor':soprano[2].id,
                    'name':'Test paradigm','label':'Test paradigm'}]
            annotated_xml(source,target,[],score=score,paradigm_marks=marks)
            self.assertEqual(read_ranked(target)[0],score)
            root=ET.parse(target).getroot()
            starts=[m.get('number') for m in root.findall('part/measure') if m.find("direction/direction-type/bracket[@type='start']") is not None]
            stops=[m.get('number') for m in root.findall('part/measure') if m.find("direction/direction-type/bracket[@type='stop']") is not None]
            self.assertEqual(starts,['1'])
            self.assertEqual(stops,['3'])

    def test_incomplete_seventh_is_contextual_and_label_variants_normalize(self):
        score=example()
        notes=tuple(Note(n.id,n.voice,n.measure,n.measure_index,n.beat,n.duration,
                         Pitch.parse({'S':'G5','A':'E4','T':'D4','B':'E3'}[n.voice])) for n in score.notes)
        score=Score(notes,score.measures,1)
        harmony=review_harmony(score,[])
        self.assertEqual(harmony[0]['roman'],'vi7')
        self.assertEqual(harmony[0]['status'],'interpreted')
        self.assertEqual(harmony[0]['omitted'],'B')
        for text,expected in [('V65','V6/5'),('viio64','vii°6/4'),('vii07','viiø7'),('V42','V4/2'),('HC',None)]:
            self.assertEqual(canonical_label(text),expected)

    def test_extended_length_does_not_create_a_musical_error(self):
        score=example()
        longer=Score(tuple(Note(f'{n.id}-{i}',n.voice,str(i*4+n.measure_index+1),i*4+n.measure_index,n.beat,n.duration,n.pitch)
                           for i in range(3) for n in score.notes),tuple(str(i) for i in range(1,13)),0)
        self.assertNotIn('measure_count',[f['rule'] for f in check(longer,constraints_for(longer),enforce_length=False)])


if __name__=='__main__':
    unittest.main()
