function createTable() {
    let bill_data = JSON.parse(document.getElementById('bill_data').textContent);

    console.log(bill_data);
    console.log(typeof bill_data);
    let tableHTML = '<table class="table table-bordered table-small table-hover"><tr><thead><th>Latest Update</th><th>Bill ID</th><th>Title</th><th>Source</tr></thead>';
    Object.keys(bill_data).forEach(key => {
        tableHTML += '<tr>';
        tableHTML += '<td>' + bill_data[key]["updateDate"] + '</td>';
        tableHTML += '<td><a href="bill/' + bill_data[key]['congress'] + '/' + bill_data[key]['type'] + '/' + bill_data[key]['number'] + '">' + bill_data[key]["type"] + bill_data[key]["number"] + '</a></td>';
        tableHTML += '<td>' + bill_data[key]["title"] + '</td>';
        tableHTML += '<td>' + bill_data[key]["originChamber"] + '</td>';
        tableHTML += '</tr>';
    });

    tableHTML += '</table>';
    document.body.innerHTML += tableHTML;
}

createTable();