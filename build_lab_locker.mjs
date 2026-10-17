import fs from "node:fs/promises";
import { SpreadsheetFile, Workbook } from "@oai/artifact-tool";

const mode = process.argv[2] ?? "baseline";
const isRag = mode === "rag";
const outDir = "outputs/rag-comparison";
const stem = isRag ? "lab_locker_rag" : "lab_locker_baseline";
await fs.mkdir(outDir, { recursive: true });

const c = (medium, small, scenario, pre, steps, expected, rule) => ({ medium, small, scenario, pre, steps, expected, rule });
const cases = [
  c("예약", "일반 시약", "AVAILABLE 상태의 일반 시약을 예약할 시, 예약이 생성되고 시약이 RESERVED 상태로 변경되는지 확인", ["연구원 계정으로 로그인함", "일반 시약 상태가 AVAILABLE임"], ["일반 시약을 선택한다", "예약을 요청한다", "예약 내역과 시약 상태를 조회한다"], "예약이 생성되고 시약 상태가 RESERVED로 변경된다.", "예약 규칙 1~2"),
  c("예약", "위험 시약", "위험 시약을 예약하고 승인자가 승인할 시, 예약이 확정되는지 확인", ["위험 시약 상태가 AVAILABLE임", "연구원과 승인자 계정이 존재함"], ["연구원이 위험 시약 예약을 요청한다", "승인자가 요청을 승인한다", "예약과 시약 상태를 조회한다"], "승인 후 예약이 확정되고 시약 상태가 RESERVED로 변경된다.", "예약 규칙 3"),
  c("예약", "위험 시약", "위험 시약 예약이 승인 대기 중일 시, 다른 연구원이 같은 시약을 예약할 수 없는지 확인", ["위험 시약 상태가 AVAILABLE임", "연구원 계정 2개가 존재함"], ["연구원 A가 위험 시약 예약을 요청한다", "승인 전에 연구원 B가 같은 시약 예약을 요청한다", "두 요청과 시약 상태를 확인한다"], "시약 상태는 AVAILABLE로 유지되지만 연구원 B의 예약은 생성되지 않는다.", "예약 규칙 4"),
  c("예약", "위험 시약", "승인자가 위험 시약 예약을 반려할 시, 예약이 확정되지 않는지 확인", ["위험 시약 예약이 승인 대기 중임"], ["승인자가 예약을 반려한다", "예약 내역과 시약 상태를 조회한다"], "예약이 확정되지 않는다. 반려 이후 시약 상태는 요구사항에 명시되지 않아 확인이 필요하다.", "예약 규칙 3, 승인 반려 후 상태 확인 필요"),
  c("예약", "예약 한도", "연구원이 활성 예약 3건을 보유한 상태에서 네 번째 예약을 요청할 시, 추가 예약이 생성되지 않는지 확인", ["연구원에게 활성 예약 3건이 존재함", "추가 일반 시약이 AVAILABLE 상태임"], ["네 번째 시약 예약을 요청한다", "예약 목록과 추가 시약 상태를 조회한다"], "네 번째 활성 예약은 생성되지 않는다.", "예약 규칙 5"),
  c("예약", "예약 만료", "예약 생성 후 10분 안에 수령하지 않을 시, 예약이 자동 취소되는지 확인", ["일반 시약 예약이 생성됨", "시스템 시간을 조정할 수 있음"], ["예약 생성 시각을 기록한다", "수령하지 않고 시스템 시간을 10분 이후로 이동한다", "예약과 시약 상태를 조회한다"], "예약이 자동 취소되고 시약 상태가 AVAILABLE로 변경된다.", "예약 규칙 6~7"),
  c("예약", "동시 예약", "두 연구원이 AVAILABLE 상태의 동일 시약을 동시에 예약할 시, 한 건만 성공하는지 확인", ["동일 시약이 AVAILABLE 상태임", "연구원 계정 2개와 동시 요청 도구가 존재함"], ["두 계정으로 동일 시약 예약을 동시에 전송한다", "두 응답과 생성된 예약 건수를 확인한다"], "먼저 완료된 요청 한 건만 성공하고 활성 예약은 한 건만 생성된다.", "예약 규칙 8"),
  c("예약", "중복 요청", "동일한 request_id로 예약을 반복 요청할 시, 예약이 중복 생성되지 않는지 확인", ["예약 가능한 일반 시약이 존재함"], ["고정 request_id로 예약을 요청한다", "같은 request_id로 동일 요청을 다시 전송한다", "응답과 예약 건수를 확인한다"], "두 요청은 최초 결과를 반환하고 예약은 한 건만 생성된다.", "예약 규칙 9"),
  c("예약", "예약 금지 상태", "EXPIRED, EMPTY 또는 INSPECTION 상태의 시약을 예약할 시, 예약이 생성되지 않는지 확인", ["각 상태의 시약이 준비됨"], ["각 시약에 대해 예약을 요청한다", "예약 생성 여부와 시약 상태를 확인한다"], "세 상태 모두 예약이 생성되지 않는다.", "예약 규칙 10"),
  c("수령", "정상 수령", "예약한 연구원이 유효한 QR 코드로 시약을 수령할 시, 시약이 CHECKED_OUT 상태로 변경되는지 확인", ["유효한 RESERVED 예약과 지정 보관함이 존재함"], ["예약 연구원이 QR 코드를 스캔한다", "문이 열리면 시약을 꺼낸다", "문을 닫고 상태를 조회한다"], "지정 보관함 문이 열리고 문을 닫은 후 시약 상태가 CHECKED_OUT으로 변경된다.", "수령 규칙 1~5"),
  c("수령", "사용자 검증", "예약하지 않은 사용자가 예약 QR 코드를 사용할 시, 수령이 거부되는지 확인", ["연구원 A의 유효한 예약이 존재함", "연구원 B가 로그인함"], ["연구원 B가 연구원 A의 QR 코드를 스캔한다", "보관함과 예약 상태를 확인한다"], "QR 사용이 거부되고 보관함 문이 열리지 않는다.", "수령 규칙 1, 7"),
  c("수령", "QR 유효성", "이미 사용한 QR 코드를 다시 사용할 시, 수령이 거부되는지 확인", ["QR 코드로 수령이 한 번 완료됨"], ["동일한 QR 코드를 다시 스캔한다", "보관함 문과 이력을 확인한다"], "QR 사용이 거부되고 추가 수령이 발생하지 않는다.", "수령 규칙 4, 7"),
  c("수령", "QR 유효성", "예약 만료 후 QR 코드를 사용할 시, 수령이 거부되는지 확인", ["예약 QR이 발급됨", "예약 생성 후 10분이 지남"], ["만료된 QR 코드를 스캔한다", "보관함 문과 예약 상태를 확인한다"], "QR 사용이 거부되고 보관함 문이 열리지 않는다.", "예약 규칙 6~7, 수령 규칙 2, 7"),
  c("수령", "문 열림 경고", "보관함 문이 열린 후 30초 동안 닫히지 않을 시, 경고가 발생하는지 확인", ["유효한 예약으로 보관함 문을 열 수 있음", "시스템 시간을 관찰할 수 있음"], ["QR을 스캔해 문을 연다", "문을 닫지 않고 30초 동안 유지한다", "경고 발생 여부를 확인한다"], "문이 열린 후 30초 동안 닫히지 않으면 경고가 발생한다.", "수령 규칙 6"),
  c("수령", "보관함 상태", "LOCKED 또는 ERROR 상태의 보관함에서 수령을 시도할 시, 문이 열리지 않는지 확인", ["유효한 예약이 존재함", "보관함 상태를 LOCKED와 ERROR로 변경할 수 있음"], ["각 상태에서 예약 QR을 스캔한다", "문 열림 여부와 처리 결과를 확인한다"], "두 상태 모두 보관함 문이 열리지 않는다.", "수령 규칙 8"),
  c("반납", "정상 반납", "CHECKED_OUT 시약을 기준 무게로 반납할 시, 반납이 완료되는지 확인", ["시약 상태가 CHECKED_OUT임", "사용 가능한 보관함이 존재함"], ["반납 QR을 스캔한다", "배정된 보관함에 시약을 넣고 문을 닫는다", "무게와 시약 상태를 확인한다"], "측정 무게가 기준 무게의 ±5% 이내이면 반납이 완료되고 시약 상태가 AVAILABLE로 변경된다.", "반납 규칙 1~6"),
  c("반납", "무게 경계값", "측정 무게가 기준 무게의 95% 또는 105%일 시, 정상 반납되는지 확인", ["시약 상태가 CHECKED_OUT임", "무게를 경계값으로 설정할 수 있음"], ["기준 무게의 95%로 반납한다", "별도 시약을 기준 무게의 105%로 반납한다", "각 반납 상태를 확인한다"], "95%와 105%는 허용 범위에 포함되어 두 반납 모두 완료된다.", "반납 규칙 4"),
  c("반납", "무게 범위 초과", "측정 무게가 허용 범위를 벗어날 시, 관리자 확인 대상으로 유지되는지 확인", ["시약 상태가 CHECKED_OUT임", "무게를 95% 미만 또는 105% 초과로 설정할 수 있음"], ["허용 범위를 벗어난 무게로 시약을 넣고 문을 닫는다", "시약 상태와 관리자 요청을 확인한다"], "반납은 완료되지 않고 시약 상태가 RETURN_PENDING으로 유지되며 관리자 확인이 요청된다.", "반납 규칙 5"),
  c("반납", "만료 시약", "반납 시점에 유효기간이 지난 시약을 정상 무게로 반납할 시, EXPIRED 상태가 되는지 확인", ["CHECKED_OUT 시약의 유효기간이 지남"], ["반납 QR을 스캔한다", "시약을 넣고 문을 닫는다", "무게 확인 후 시약 상태를 조회한다"], "정상 무게로 반납이 처리되지만 시약 상태는 AVAILABLE이 아니라 EXPIRED가 된다.", "반납 규칙 7"),
  c("반납", "중복 요청", "동일한 반납 request_id를 반복 전송할 시, 반납 이력이 중복 생성되지 않는지 확인", ["반납 가능한 CHECKED_OUT 시약이 존재함"], ["고정 request_id로 반납을 완료한다", "같은 request_id로 요청을 다시 전송한다", "반납 이력 건수를 확인한다"], "반납 이력은 한 건만 생성된다.", "반납 규칙 8"),
  c("장애 처리", "오프라인 시작", "보관함이 OFFLINE 상태일 시, 신규 수령과 신규 반납을 시작할 수 없는지 확인", ["보관함 상태가 OFFLINE임", "수령 예약과 반납 대상 시약이 존재함"], ["신규 수령을 시도한다", "신규 반납을 시도한다", "보관함과 업무 상태를 확인한다"], "신규 수령과 신규 반납이 모두 시작되지 않는다.", "오프라인 규칙 1"),
  c("장애 처리", "오프라인 복구", "문이 열린 후 네트워크가 끊겼다가 복구될 시, 로컬 결과가 서버에 한 번만 반영되는지 확인", ["수령 또는 반납 과정에서 문이 열림", "네트워크 상태를 변경할 수 있음"], ["문이 열린 후 네트워크를 끊는다", "문을 닫고 무게 측정을 완료한다", "네트워크를 복구한다", "서버 이력과 상태 반영 횟수를 확인한다"], "문 닫힘과 무게 결과가 로컬에 저장되고 복구 후 서버에 한 번만 전송된다.", "오프라인 규칙 2~3"),
  c("장애 처리", "전송 재시도", "오프라인 결과의 서버 전송이 세 번 모두 실패할 시, 관리자 확인 대상으로 기록되는지 확인", ["전송할 로컬 결과가 존재함", "서버 전송 실패를 발생시킬 수 있음"], ["네트워크를 복구한다", "서버 전송을 세 번 연속 실패시킨다", "재시도 횟수와 관리자 확인 기록을 조회한다"], "서버 전송을 최대 3회 재시도하고 모두 실패하면 관리자 확인 대상으로 기록한다.", "오프라인 규칙 4~5"),
  c("장애 처리", "장치 오류", "반납 중 센서 오류가 발생할 시, 반납 성공으로 처리되지 않는지 확인", ["CHECKED_OUT 시약과 사용 가능한 보관함이 존재함", "센서 오류를 발생시킬 수 있음"], ["반납을 시작한다", "문을 닫을 때 센서 오류를 발생시킨다", "반납 결과와 시약 상태를 확인한다"], "반납은 성공으로 처리되지 않는다. 이후 시약 상태는 요구사항에 명시되지 않아 확인이 필요하다.", "오프라인 규칙 6"),
  c("장애 처리", "장치 오류", "수령 중 잠금장치 오류가 발생할 시, 문 열림 성공으로 처리되지 않는지 확인", ["유효한 예약이 존재함", "잠금장치 오류를 발생시킬 수 있음"], ["예약 QR을 스캔한다", "잠금장치 오류를 발생시킨다", "문과 수령 상태를 확인한다"], "문 열림 성공으로 처리되지 않고 수령이 완료되지 않는다.", "오프라인 규칙 7"),
  c("감사", "이력 기록", "예약부터 반납까지 성공·실패 작업을 수행할 시, 필수 감사 정보가 기록되는지 확인", ["연구원, 승인자, 관리자 계정이 존재함", "성공 및 실패 요청을 수행할 수 있음"], ["예약, 승인 또는 반려, 자동 취소, 수령, 반납, 관리자 확인 작업을 수행한다", "성공 및 실패 감사 이력을 조회한다", "각 이력의 필드를 확인한다"], "각 이력에 사용자, 시약, 보관함, 처리 시각, request_id, 처리 결과가 기록되고 실패 요청에는 실패 원인이 포함된다.", "감사 기록 규칙 1~3"),
  c("감사", "조회 권한", "일반 연구원이 다른 사용자의 감사 기록을 조회할 시, 기록이 노출되지 않는지 확인", ["연구원 A와 B의 감사 기록이 존재함", "연구원 A로 로그인함"], ["연구원 A가 연구원 B의 감사 기록을 조회한다", "조회 결과를 확인한다"], "연구원 B의 감사 기록이 연구원 A에게 노출되지 않는다.", "감사 기록 규칙 4"),
];

const ragRefs = {
  "위험 시약": "패턴 참고: rec_40dad1a53a2945fca52302cbdac9378d, rec_6697c45e4bc840a7bdcaf7cca3633c2e (승인·반려)",
  "사용자 검증": "패턴 참고: rec_215900f632ac4dd9a28eff5055db7d19 (역할 기반 접근 차단)",
  "조회 권한": "패턴 참고: rec_215900f632ac4dd9a28eff5055db7d19 (역할 기반 접근 차단)",
  "이력 기록": "패턴 참고: rec_aa38f405d69f48cb9c822fc01effac6c (감사 기록)",
};

const rows = cases.map((x, i) => [
  "시약 보관함 관리", x.medium, x.small, `${isRag ? "GEN-LAB-RAG" : "GEN-LAB-BASE"}-${String(i + 1).padStart(3, "0")}`,
  x.scenario,
  `[사전조건]\n${x.pre.map(v => `- ${v}`).join("\n")}\n\n[수행 절차]\n${x.steps.map((v, n) => `${n + 1}. ${v}`).join("\n")}`,
  x.expected, "", "",
  `기대결과 근거: 사용자 제공 요구사항\n적용 규칙: ${x.rule}${isRag && ragRefs[x.small] ? `\n${ragRefs[x.small]}\n다른 제품의 정책은 사용하지 않음` : ""}`,
]);

const workbook = Workbook.create();
const sheet = workbook.worksheets.add("테스트케이스");
sheet.showGridLines = false;
sheet.mergeCells("A1:J1");
sheet.getRange("A1").values = [[`LAB-LOCKER 1.0 - ${isRag ? "로컬 RAG" : "기본 LLM"} 생성 TC 검토본`]];
sheet.getRange("I2:J2").merge(); sheet.getRange("I2").values = [["작성자:"]];
sheet.getRange("I3:J3").merge(); sheet.getRange("I3").values = [["검토자:"]];
sheet.mergeCells("A4:C4");
for (const col of ["D","E","F","G","H","I","J"]) sheet.mergeCells(`${col}4:${col}5`);
sheet.getRange("A4:J5").values = [
  ["기능명",null,null,"TC_ID","테스트 시나리오","입력\n(사전조건 포함)","기대 출력\n(사후조건 포함)","테스트 결과\n(P:Pass, F:Fail)","상세 테스트 결과\n(F인 경우 결함 요약)","비고"],
  ["대분류","중분류","소분류",null,null,null,null,null,null,null],
];
sheet.getRangeByIndexes(5, 0, rows.length, 10).values = rows;

for (const col of [0,1,2]) {
  let start=0;
  while (start<rows.length) {
    let end=start;
    while (end+1<rows.length && rows[end+1][col]===rows[start][col]) end++;
    if (end>start) sheet.mergeCells(`${String.fromCharCode(65+col)}${start+6}:${String.fromCharCode(65+col)}${end+6}`);
    start=end+1;
  }
}

const last=rows.length+5;
sheet.getRange(`A1:J${last}`).format.font = { name:"Arial", size:10, color:"#1F2937" };
sheet.getRange("A1:J1").format = { font:{name:"Arial",size:16,bold:true,color:"#1F2937"}, horizontalAlignment:"center", verticalAlignment:"center", rowHeight:30 };
sheet.getRange("I2:J3").format = { font:{name:"Arial",size:10,color:"#4B5563"}, horizontalAlignment:"left" };
sheet.getRange("A4:J5").format = { fill:"#1F4E78", font:{name:"Arial",size:10,bold:true,color:"#FFFFFF"}, horizontalAlignment:"center", verticalAlignment:"center", wrapText:true, borders:{preset:"all",style:"thin",color:"#FFFFFF"} };
sheet.getRange(`A6:J${last}`).format = { verticalAlignment:"top", wrapText:true, borders:{preset:"all",style:"thin",color:"#D1D5DB"} };
sheet.getRange(`A6:D${last}`).format.horizontalAlignment = "center";
sheet.getRange(`J6:J${last}`).format.fill = isRag ? "#E8F1FB" : "#F3F4F6";
sheet.getRange(`H6:I${last}`).format.fill = "#F9FAFB";
const widths=[18,16,18,18,42,54,42,16,28,36];
for (let col=0; col<10; col++) sheet.getRangeByIndexes(0,col,last,1).format.columnWidth=widths[col];
sheet.getRange("A4:J5").format.rowHeight=28;
sheet.getRange(`A6:J${last}`).format.rowHeight=100;
sheet.freezePanes.freezeRows(5); sheet.freezePanes.freezeColumns(4);
workbook.recalculate();
console.log((await workbook.inspect({kind:"table",range:`테스트케이스!A1:J${Math.min(last,10)}`,include:"values,formulas",tableMaxRows:10,tableMaxCols:10,maxChars:10000})).ndjson);
console.log((await workbook.inspect({kind:"match",searchTerm:"#REF!|#DIV/0!|#VALUE!|#NAME\\?|#N/A|#NUM!|#NULL!|#SPILL!|#CALC!",options:{useRegex:true,maxResults:100},summary:"formula errors"})).ndjson);
const preview=await workbook.render({sheetName:"테스트케이스",range:`A1:J${last}`,scale:.7,format:"png"});
await fs.writeFile(`${outDir}/${stem}.png`,new Uint8Array(await preview.arrayBuffer()));
const output=await SpreadsheetFile.exportXlsx(workbook); await output.save(`${outDir}/${stem}.xlsx`);
console.log(JSON.stringify({mode,count:rows.length,output:`${outDir}/${stem}.xlsx`,preview:`${outDir}/${stem}.png`}));
