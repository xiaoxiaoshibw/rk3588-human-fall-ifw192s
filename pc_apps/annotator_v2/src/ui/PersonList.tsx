// ui/PersonList.tsx — 人物列表：目标人物（画框去向）显式选择。
import React, { useState } from "react";
import type { AnnotationDoc, Box, Person } from "../domain/types.ts";

export interface PersonListProps {
  doc: AnnotationDoc | null;
  boxesThisFrame: Box[];
  targetPersonId: string | null;
  setTargetPersonId(v: string | null): void;
  onAddPerson(): void;
  onRemovePerson(personId: string): void;
  personColorOf(doc: AnnotationDoc | null, personId: string): string;
}

export function PersonList(p: PersonListProps) {
  const [confirmRemove, setConfirmRemove] = useState<string | null>(null);
  const persons = p.doc?.persons ?? [];
  const boxCount = (personId: string) => p.doc?.boxes.filter((b) => b.personId === personId).length ?? 0;
  const frameBox = (personId: string) => p.boxesThisFrame.find((b) => b.personId === personId);

  return (
    <>
      <h4>人物</h4>
      <div style={{ display: "flex", gap: 4, marginBottom: 6 }}>
        <button onClick={p.onAddPerson} title="新增人物（自动编号 P1/P2…）">＋ 人物</button>
      </div>
      {persons.length === 0 && <div className="status-msg">还没有人物。点「＋人物」，或直接切「画框」会自动建 P1。</div>}
      {persons.map((person: Person) => (
        <div
          key={person.personId}
          className={"person-item" + (p.targetPersonId === person.personId ? " target" : "")}
          onClick={() => p.setTargetPersonId(person.personId)}
          title="点击设为画框目标"
        >
          <span className="swatch" style={{ background: p.personColorOf(p.doc, person.personId) }} />
          <span className="name">{person.personId}</span>
          <span className="meta">{boxCount(person.personId)} 框{frameBox(person.personId) ? " · 本帧✓" : ""}</span>
          {confirmRemove === person.personId ? (
            <>
              <button className="small danger" onClick={(e) => { e.stopPropagation(); p.onRemovePerson(person.personId); setConfirmRemove(null); }}>确认删</button>
              <button className="small" onClick={(e) => { e.stopPropagation(); setConfirmRemove(null); }}>取消</button>
            </>
          ) : (
            <button className="small danger" title="删除人物及其全部框/区间"
              onClick={(e) => { e.stopPropagation(); setConfirmRemove(person.personId); }}>删</button>
          )}
        </div>
      ))}
      <h4>说明</h4>
      <div className="status-msg">
        「画框」工具在画布拖动建框，松手自动回「选择」。<br />
        画框落到当前目标人物（列表点击切换）。<br />
        中键拖动随时平移；滚轮缩放。
      </div>
    </>
  );
}
