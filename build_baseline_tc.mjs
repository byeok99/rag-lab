import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const mode = process.argv[2] ?? "baseline";
const outputDir = "outputs/rag-comparison";
const outputPath = `${outputDir}/${mode === "rag" ? "rag_cli_online_index_tc" : "baseline_llm_online_index_tc"}.xlsx`;
const previewPath = `${outputDir}/${mode === "rag" ? "rag_cli_online_index_tc" : "baseline_llm_online_index_tc"}.png`;
await fs.mkdir(outputDir, { recursive: true });

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("테스트케이스");
sheet.showGridLines = false;

sheet.mergeCells("A1:J1");
sheet.getRange("A1").values = [[mode === "rag" ? "온라인 인덱스 생성 중 데이터 변경 처리 - 로컬 RAG 생성 TC 검토본" : "온라인 인덱스 생성 중 데이터 변경 처리 - 기본 LLM 생성 TC 검토본"]];
sheet.getRange("I2:J2").merge();
sheet.getRange("I2").values = [["작성자:"]];
sheet.getRange("I3:J3").merge();
sheet.getRange("I3").values = [["검토자:"]];

sheet.mergeCells("A4:C4");
sheet.mergeCells("D4:D5");
sheet.mergeCells("E4:E5");
sheet.mergeCells("F4:F5");
sheet.mergeCells("G4:G5");
sheet.mergeCells("H4:H5");
sheet.mergeCells("I4:I5");
sheet.mergeCells("J4:J5");
sheet.getRange("A4:J5").values = [
  ["기능명", null, null, "TC_ID", "테스트 시나리오", "입력\n(사전조건 포함)", "기대 출력\n(사후조건 포함)", "테스트 결과\n(P:Pass, F:Fail)", "상세 테스트 결과\n(F인 경우 결함 요약)", "비고"],
  ["대분류", "중분류", "소분류", null, null, null, null, null, null, null],
];

const baselineRows = [
  [
    "데이터베이스", "인덱스", "온라인 인덱스", "GEN-BASE-0001",
    "온라인 인덱스를 생성하는 중 동일 테이블에 데이터를 추가할 시, 추가 작업과 인덱스 생성 결과가 일관되게 처리되는지 확인",
    "[사전조건]\n- 대량 데이터가 저장된 테스트 테이블이 존재함\n- 대상 컬럼에 온라인 인덱스를 생성할 수 있음\n- 두 개의 독립된 사용자 세션을 사용할 수 있음\n\n[수행 절차]\n1. 사용자 A가 대상 테이블의 온라인 인덱스 생성을 시작한다.\n2. 인덱스 생성 진행 상태를 확인한다.\n3. 사용자 B가 동일 테이블에 신규 데이터를 추가한다.\n4. 추가 작업의 성공, 실패 또는 대기 상태를 기록한다.\n5. 인덱스 생성 완료 후 추가 데이터를 조회한다.\n6. 인덱스를 사용하는 조회에 추가 데이터가 포함되는지 확인한다.",
    "확인 필요\n- 인덱스 생성 중 INSERT 허용 여부\n- 추가 데이터의 인덱스 반영 시점",
    "", "",
    "기대결과 근거: unknown\n확인 필요: 예",
  ],
  [
    "데이터베이스", "인덱스", "온라인 인덱스", "GEN-BASE-0002",
    "온라인 인덱스를 생성하는 중 동일 테이블의 데이터를 수정할 시, 수정 작업과 인덱스 생성 결과가 일관되게 처리되는지 확인",
    "[사전조건]\n- 수정 가능한 데이터가 저장된 테스트 테이블이 존재함\n- 두 개의 독립된 사용자 세션을 사용할 수 있음\n\n[수행 절차]\n1. 변경 대상 데이터의 현재 값을 조회해 기록한다.\n2. 사용자 A가 온라인 인덱스 생성을 시작한다.\n3. 사용자 B가 기존 데이터의 인덱스 대상 컬럼 또는 관련 컬럼을 수정한다.\n4. 수정 작업의 성공, 실패 또는 대기 상태를 기록한다.\n5. 인덱스 생성 완료 후 수정 조건으로 데이터를 조회한다.\n6. 인덱스 사용 여부와 조회 결과를 확인한다.",
    "확인 필요\n- 인덱스 생성 중 UPDATE 허용 여부\n- 인덱스 대상/비대상 컬럼 수정 정책",
    "", "",
    "기대결과 근거: unknown\n확인 필요: 예",
  ],
  [
    "데이터베이스", "인덱스", "온라인 인덱스", "GEN-BASE-0003",
    "온라인 인덱스 생성 중 데이터 추가와 수정을 반복할 시, 작업 누락이나 데이터 불일치가 발생하지 않는지 확인",
    "[사전조건]\n- 반복 변경 가능한 테스트 데이터가 존재함\n- 인덱스 생성과 데이터 변경을 병렬 수행할 수 있음\n\n[수행 절차]\n1. 사용자 A가 온라인 인덱스 생성을 시작한다.\n2. 사용자 B가 데이터 추가와 수정을 반복 실행한다.\n3. 각 요청의 건수와 처리 상태를 기록한다.\n4. 인덱스 생성 완료 후 테이블 데이터를 조회한다.\n5. 성공한 변경 요청과 실제 저장 데이터를 비교한다.\n6. 인덱스 조회 결과와 전체 조회 결과를 비교한다.",
    "확인 필요\n- 반복 횟수와 데이터 규모\n- 대기, 실패, 재시도 요청의 판정 기준",
    "", "",
    "기대결과 근거: unknown\n확인 필요: 예",
  ],
  [
    "데이터베이스", "인덱스", "온라인 인덱스", "GEN-BASE-0004",
    "온라인 인덱스 생성 중 데이터 변경이 실패하거나 중단될 시, 인덱스와 테이블이 복구 가능한 상태로 유지되는지 확인",
    "[사전조건]\n- 온라인 인덱스 생성과 데이터 변경을 동시에 수행할 수 있음\n- 작업 상태와 오류를 관찰할 수 있음\n\n[수행 절차]\n1. 사용자 A가 온라인 인덱스 생성을 시작한다.\n2. 사용자 B가 동일 테이블의 데이터를 추가하거나 수정한다.\n3. 데이터 변경이 실패하거나 중단되는 상황을 발생시킨다.\n4. 인덱스 생성 작업 상태를 확인한다.\n5. 실패한 변경의 반영 여부를 확인한다.\n6. 완료 후 테이블과 인덱스를 이용한 조회를 수행한다.\n7. 재시도 또는 복구 절차 필요 여부를 확인한다.",
    "확인 필요\n- 허용된 실패 유발 방법\n- 자동 롤백, 재시도 및 인덱스 정리 정책",
    "", "",
    "기대결과 근거: unknown\n확인 필요: 예",
  ],
];
const ragRows = [
  [
    "데이터베이스 엔진", "온라인 관리", "온라인 인덱스", "GEN-RAG-0001",
    "온라인 인덱스를 생성하는 중 동일 테이블에 데이터를 추가할 시, 추가 데이터가 인덱스 생성 완료 후 정상적으로 조회되는지 확인",
    "[사전조건]\n- 관리자 계정으로 데이터베이스에 접속함\n- tta_online_index_test 테이블에 기본 데이터 5,000,000건이 존재함\n- tta_insert_load(BIGINT, INTEGER) 프로시저가 존재함\n- 두 개의 독립된 터미널을 사용할 수 있음\n\n[수행 절차]\n1. 터미널 2에서 CALL public.tta_insert_load(20000000, 20000);를 실행한다.\n2. INSERT 수행 중 터미널 1에서 CREATE INDEX CONCURRENTLY idx_tta_online_search ON public.tta_online_index_test(search_key);를 실행한다.\n3. 인덱스 생성 완료 후 추가한 ID 범위의 데이터 건수를 조회한다.",
    "추가한 ID 범위의 조회 건수가 20,000건으로 출력되는지 확인한다.",
    "", "",
    "근거: rec_78e3f7466eb24c02aa142504ec0c7c4a\n원본 위치: 테스트케이스 48행\n근거 유형: existing_tc\n기존 TC와 완전 중복 가능성 높음",
  ],
  [
    "데이터베이스 엔진", "온라인 관리", "온라인 인덱스", "GEN-RAG-0002",
    "온라인 인덱스를 생성하는 중 동일 테이블의 데이터를 수정할 시, 수정 데이터가 인덱스 생성 완료 후 정상적으로 조회되는지 확인",
    "[사전조건]\n- 관리자 계정으로 데이터베이스에 접속함\n- tta_online_index_test 테이블에 기본 데이터 5,000,000건이 존재함\n- tta_update_load(BIGINT, INTEGER) 프로시저가 존재함\n- 두 개의 독립된 터미널을 사용할 수 있음\n\n[수행 절차]\n1. 터미널 2에서 CALL public.tta_update_load(0, 20000);를 실행한다.\n2. 데이터 변경 중 터미널 1에서 CREATE INDEX CONCURRENTLY idx_tta_online_search ON public.tta_online_index_test(search_key);를 실행한다.\n3. 인덱스 생성 완료 후 value_text LIKE 'ROUND2_UPDATE_%' 조건으로 데이터 건수를 조회한다.",
    "조회 건수가 20,000건으로 출력되는지 확인한다.",
    "", "",
    "근거: rec_8262ce92fc034b3e848878c234ac0053\n원본 위치: 테스트케이스 51행\n근거 유형: existing_tc\n기존 TC와 완전 중복 가능성 높음",
  ],
  [
    "데이터베이스 엔진", "온라인 관리", "온라인 인덱스", "GEN-RAG-0003",
    "온라인 인덱스 생성 중 동일 테이블에 데이터 추가와 수정을 함께 수행할 시, 성공한 변경 데이터가 완료 후 조회되는지 확인",
    "[사전조건]\n- 대량 데이터가 저장된 tta_online_index_test 테이블이 존재함\n- INSERT와 UPDATE를 독립적으로 수행할 수 있음\n- 세 개의 독립된 터미널을 사용할 수 있음\n\n[수행 절차]\n1. 터미널 1에서 온라인 인덱스 생성을 시작한다.\n2. 생성 중 터미널 2에서 신규 데이터를 추가한다.\n3. 동시에 터미널 3에서 기존 데이터를 수정한다.\n4. 각 요청의 성공, 실패 또는 대기 상태를 기록한다.\n5. 인덱스 생성 완료 후 성공한 INSERT와 UPDATE 대상 데이터를 각각 조회한다.",
    "확인 필요\n- INSERT와 UPDATE를 함께 수행할 때의 허용 정책\n- 성공한 각 변경이 인덱스 조회에 반영되어야 하는 시점",
    "", "",
    "근거: rec_78e3f7466eb24c02aa142504ec0c7c4a, rec_8262ce92fc034b3e848878c234ac0053\n근거 유형: inferred\n확인 필요: 예",
  ],
  [
    "데이터베이스 엔진", "온라인 관리", "온라인 인덱스", "GEN-RAG-0004",
    "온라인 인덱스 생성 중 데이터 변경 작업이 실패할 시, 인덱스 생성과 데이터 상태를 확인하고 변경 작업을 재시도할 수 있는지 확인",
    "[사전조건]\n- 온라인 인덱스 생성과 데이터 변경을 동시에 수행할 수 있음\n- 각 작업의 오류 및 트랜잭션 상태를 확인할 수 있음\n\n[수행 절차]\n1. 온라인 인덱스 생성을 시작한다.\n2. 동일 테이블에 데이터 추가 또는 수정을 수행한다.\n3. 변경 작업이 실패한 경우 오류와 트랜잭션 상태를 기록한다.\n4. 인덱스 생성 완료 여부와 인덱스 상태를 확인한다.\n5. 실패한 변경 작업을 다시 수행한다.\n6. 재시도한 데이터와 인덱스 조회 결과를 확인한다.",
    "확인 필요\n- 실패 유발 조건과 오류 메시지\n- 롤백, 재시도 및 인덱스 유지 정책",
    "", "",
    "관련 근거: 온라인 INSERT/UPDATE TC\n직접 근거 없음\n근거 유형: unknown\n확인 필요: 예",
  ],
];
const rows = mode === "rag" ? ragRows : baselineRows;
sheet.getRange("A6:J9").values = rows;
sheet.mergeCells("A6:A9");
sheet.mergeCells("B6:B9");
sheet.mergeCells("C6:C9");

sheet.getRange("A1:J9").format.font = { name: "Arial", size: 10, color: "#1F2937" };
sheet.getRange("A1:J1").format = {
  font: { name: "Arial", size: 16, bold: true, color: "#1F2937" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
};
sheet.getRange("A1:J1").format.rowHeight = 30;
sheet.getRange("I2:J3").format = { font: { name: "Arial", size: 10, color: "#4B5563" }, horizontalAlignment: "left" };
sheet.getRange("A4:J5").format = {
  fill: "#1F4E78",
  font: { name: "Arial", size: 10, bold: true, color: "#FFFFFF" },
  horizontalAlignment: "center",
  verticalAlignment: "center",
  wrapText: true,
  borders: { preset: "all", style: "thin", color: "#FFFFFF" },
};
sheet.getRange("A6:J9").format = {
  verticalAlignment: "top",
  wrapText: true,
  borders: { preset: "all", style: "thin", color: "#D1D5DB" },
};
sheet.getRange("A6:D9").format.horizontalAlignment = "center";
sheet.getRange("G6:G9").format.fill = "#FFF4CE";
sheet.getRange("J6:J9").format.fill = "#FFF4CE";
sheet.getRange("H6:I9").format.fill = "#F9FAFB";
sheet.getRange("A4:A5").format.borders = { preset: "all", style: "thin", color: "#FFFFFF" };

const widths = [17, 15, 18, 16, 42, 58, 36, 16, 28, 25];
for (let c = 0; c < widths.length; c++) sheet.getRangeByIndexes(0, c, 9, 1).format.columnWidth = widths[c];
sheet.getRange("A4:J5").format.rowHeight = 28;
sheet.getRange("A6:J9").format.rowHeight = 150;
sheet.freezePanes.freezeRows(5);
sheet.freezePanes.freezeColumns(4);
sheet.getRange("A4:J9").format.autofitRows();

workbook.recalculate();
const inspect = await workbook.inspect({ kind: "table", range: "테스트케이스!A1:J9", include: "values,formulas", tableMaxRows: 12, tableMaxCols: 10, maxChars: 10000 });
console.log(inspect.ndjson);
const errors = await workbook.inspect({ kind: "match", searchTerm: "#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!", options: { useRegex: true, maxResults: 100 }, summary: "formula errors" });
console.log(errors.ndjson);
const preview = await workbook.render({ sheetName: "테스트케이스", range: "A1:J9", scale: 1, format: "png" });
await fs.writeFile(previewPath, new Uint8Array(await preview.arrayBuffer()));
const output = await SpreadsheetFile.exportXlsx(workbook);
await output.save(outputPath);
console.log(JSON.stringify({ outputPath, previewPath }));
