import React from 'react';
import {Line} from 'react-chartjs-2';
import alpaca from '../../api/Alpaca';

export var formatter = new Intl.NumberFormat('en-US', {
    style: 'currency',
    currency: 'USD'
})

class AccountChart extends React.Component {
    constructor(props) {
        super(props);
        this.state = {};
    }

    findMaxVal = (data) => Math.max(...data);
    findMinVal = (data) => Math.min(...data);
    componentDidMount() {
        var now = new Date();
        let date_end = now.toISOString().split('T')[0]
        alpaca.getPortfolioHistory({
            date_start: "", 
            date_end: date_end, 
            timeframe: "1D",
            extended_hours: false}).then((data) => {
                let dates = data.timestamp.map((item) => {
                    var temp = new Date(0);
                    temp.setUTCSeconds(item);
                    item = temp.toLocaleString("en-US", {timeZone: "EST"});
                    item = item.substr(0, item.indexOf(','));
                    return item;
                })
                this.setState({
                    labels: dates,
                    datasets: [
                        {
                            label: 'Balance',
                            fill: 'false',
                            lineTension: 0,
                            borderColor: '#EFC3F5',
                            borderWidth: 3,
                            data: data.equity,
                            pointRadius: 0,
                            pointHoverRadius: 5,
                            pointHoverBackgroundColor: 'purple'
                        }
                    ],
                    data: data.equity,
                    min: (this.findMinVal(data.equity) - 2),
                    max: (this.findMaxVal(data.equity) + 7)
                });
            });
    }
    render() {
        return (
            <div className="account-info-chart-container">
                <Line
                    data={this.state}
                    options= {{
                        responsive: true,
                        maintainAspectRatio: false,
                        
                        scales: {
                            xAxes: [{
                                gridLines: {
                                    display: false,
                                    color: '#f4ebf5da'
                                },
                                ticks: {
                                    backdropColor: 'white',
                                    autoSkip: true,
                                    maxRotation: 0,
                                    minRotation: 0,
                                    maxTicksLimit: 4,
                                    fontFamily: "Open Sans, sans-serif",
                                    fontColor: "#f4ebf5da",
                                }
                            }],
                            yAxes: [{
                                    display: false,
                                    gridLines: {
                                        display: false
                                    },
                                    ticks: {
                                        display: false,
                                        min: this.state.min,
                                        max: this.state.max
                                    }
                            }]
                        },
                        legend: {
                            display: false
                        },
                        tooltips: {
                            mode: 'label',
                            intersect: false,
                            yAlign: 'bottom',
                            displayColors: false,
                            callbacks: {
                                label: function(tooltipItem) {
                                        return formatter.format(tooltipItem.yLabel);
                                }
                            }
                        },
                        hover: {
                            mode: 'index',
                            intersect: false,
                            ticks: {
                                display: true
                            }
                        }
                    }}/>
            </div>
        )
    }
}
export default AccountChart;