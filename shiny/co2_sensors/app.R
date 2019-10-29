    # > rsconnect::deployApp('~/repos/co2_sensor_array/shiny/co2_sensors/')

library(shiny)
library(dplyr)
library(data.table)
library(ggplot2)
library(lubridate)
library(plotly)
library(RMariaDB)

Sys.setenv(TZ='America/Vancouver')

date_ranger <-function(date_range){
    
    t <- Sys.time()
    local_t <- sprintf("%02d:%02d:%02d",hour(t),minute(t),round(second(t)))
    local_tz_datetime <- lubridate::ymd_hms(paste(date_range, local_t), tz=Sys.timezone())    
    select_datetime_range <- with_tz(local_tz_datetime, "UTC")

    return(select_datetime_range)
}
get_co2_data <- function(select_datetime_range){
    con <- DBI::dbConnect(RMariaDB::MariaDB(),
                          host = "remotemysql.com",
                          user = "rgDubOKpGu",
                          password = "qK7Ymofmms",
                          dbname = "rgDubOKpGu"
    )
    d1 <- select_datetime_range[1]
    d2 <- select_datetime_range[2]
    
    tables <- RMariaDB::dbListTables(con)
    select_tables <- function(con,name){
        tb <- RMariaDB::dbGetQuery(con, sprintf("SELECT * FROM %s WHERE T BETWEEN '%s' AND '%s'", name, d1, d2))
        out <- as.data.table(tb)
        out[,device_id := name]
        out[,CO2_ppm := PPM_10X/10]
        out[,sensor_id := as.factor(SENSOR)]
        
    }
    dt <- rbindlist(lapply(tables, select_tables, con=con))
    DBI::dbDisconnect(con) 
    dt 
}

# Define UI for application that draws a histogram
ui <- fluidPage(

    # Application title
    titlePanel("CO2 Sensor Data"),
    column(12, plotlyOutput("distPlot", height="600px")),
        
    fluidRow(
        column(2,
               dateRangeInput("dates", "Date range", start = Sys.Date() - 2, end = Sys.Date(), min = NULL,
                              max = Sys.Date(), format = "yyyy-mm-dd", startview = "month", weekstart = 0,
                              language = "en", separator = " to ", width = NULL)
        ),
        column(10,
               
               tableOutput("table")
        )
    )
    
    
)

# Define server logic required to draw a histogram
server <- function(input, output) {
    
    data_input <- reactive({
        date_range <- date_ranger(input$dates)
        dt <- get_co2_data(date_range)
        list(dt=dt,date_range=date_range)
    })
    
    output$distPlot <- renderPlotly({
        # generate bins based on input$bins from ui.R
        theme_set(theme_bw() + theme(legend.position = 'top', panel.spacing = unit(0, "line")))
        
        d <- data_input()
        pl <- ggplot(d$dt,  aes(T,CO2_ppm, colour=device_id)) +
            geom_line(colour="black", size=.5) +
            geom_point(size=1) +
            facet_grid(sensor_id ~ .) +
            scale_y_continuous(name="[CO2] (PPM)") +
            scale_x_datetime(name="Datetime (PST/PDT)", limits = d$date_range)

        ggplotly(pl) %>%
        layout(legend = list(orientation = "h", x = 0.4, y = 1.1))
    })
    output$dateText  <- renderText({
        paste("input$date is", as.character(input$dates))
    })
    
    output$table <- renderTable({
        d <- data_input()
        d$dt[,.(min=min(CO2_ppm),
                max=max(CO2_ppm),
                mean=mean(CO2_ppm),
                sd=sd(CO2_ppm),
                median=median(CO2_ppm),
                last_point = as.character(T[.N]),
                N=.N,
                avg_sampling_period = mean(diff(T))
                ),by="device_id,sensor_id"]
        
    })
}

# Run the application 
shinyApp(ui = ui, server = server)
